// postingDraftStore.ts
//
// Posting V2 durable local draft foundation. A photo/video captured in the
// composer must survive however long it takes to identify the restaurant,
// including the case where the restaurant doesn't exist in CRAVE yet at
// all. Media is moved into app-owned storage before network work begins.
//
// This store currently carries two responsibilities during the migration:
//   1. the new durable composer state (intent/reaction/caption/visibility);
//   2. the narrow #245 attach-immediately compatibility bridge used by the
//      still-live food-evidence -> add-spot flow.
//
// Responsibility (2) is intentionally temporary. It must disappear only
// when the unified composer + contribution commit path lands atomically;
// removing it earlier would strand the current production flow. Do not add
// new product behavior to that bridge.
import { AppState } from 'react-native';
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as FileSystem from 'expo-file-system/legacy';

import {
  ALLOWED_UPLOAD_TYPES,
  UploadContentType,
  confirmUpload,
  requestUpload,
  uploadToSignedUrl,
  validateUploadSize,
} from '../api/upload';
import { getCandidateStatus } from '../api/nearby';
import { useVideoQueueStore } from './videoQueueStore';
import { useToast } from '../hooks/useToast';

export type DraftMediaKind = 'photo' | 'video';
export type DraftIntent = 'private_log' | 'social_post';
export type DraftReaction = 'loved' | 'good' | 'not_for_me';
export type DraftVisibility = 'private' | 'connections' | 'public';

export type DraftRestaurantRef =
  | { type: 'unresolved' }
  | { type: 'candidate'; candidateId: string; displayName: string }
  | { type: 'place'; placeId: string };

export type DraftOutcome = 'pending' | 'awaiting_place' | 'attaching' | 'attached' | 'failed';

export interface PostingDraft {
  id: string;
  ownerId: string;
  localUri: string;
  kind: DraftMediaKind;
  mimeType?: string;
  fileSize?: number;
  restaurantRef: DraftRestaurantRef;

  // PMV2-03 composer semantics. Null means genuinely undecided; callers
  // must not infer these values from media, navigation source, or history.
  intent: DraftIntent | null;
  reaction: DraftReaction | null;
  caption: string;
  visibility: DraftVisibility | null;
  occurredAt: string | null;

  outcome: DraftOutcome;
  lastError: string | null;
  createdAt: number;
  updatedAt: number;
}

// Shape written by PR #245 before PMV2-03 added composer semantics.
// Kept explicit so persisted drafts upgrade deterministically instead of
// relying on undefined fields after hydration.
interface PostingDraftV1 {
  id: string;
  ownerId: string;
  localUri: string;
  kind: DraftMediaKind;
  mimeType?: string;
  fileSize?: number;
  restaurantRef: DraftRestaurantRef;
  outcome: 'pending' | 'attaching' | 'attached' | 'failed';
  lastError: string | null;
  createdAt: number;
}

interface PersistedDraftStateV1 {
  drafts?: PostingDraftV1[];
}

const PERSIST_VERSION = 2;

function resolveImageContentType(mimeType?: string): UploadContentType {
  if (mimeType && (ALLOWED_UPLOAD_TYPES as readonly string[]).includes(mimeType)) {
    return mimeType as UploadContentType;
  }
  return 'image/jpeg';
}

function contentTypeForVideoUri(uri: string): 'video/mp4' | 'video/quicktime' | 'video/webm' {
  const ext = uri.split('.').pop()?.toLowerCase();
  if (ext === 'mov') return 'video/quicktime';
  if (ext === 'webm') return 'video/webm';
  return 'video/mp4';
}

function generateLocalId(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

const PENDING_DRAFT_MEDIA_DIR = `${FileSystem.documentDirectory}pending_draft_media/`;

interface PostingDraftStore {
  drafts: PostingDraft[];

  createDraftFromCapture: (opts: {
    ownerId: string;
    sourceUri: string;
    kind: DraftMediaKind;
    mimeType?: string;
    fileSize?: number;
    intent?: DraftIntent | null;
  }) => Promise<PostingDraft>;

  setDraftIntent: (draftId: string, intent: DraftIntent) => void;
  setDraftReaction: (draftId: string, reaction: DraftReaction | null) => void;
  setDraftCaption: (draftId: string, caption: string) => void;
  setDraftVisibility: (draftId: string, visibility: DraftVisibility) => void;
  setDraftOccurredAt: (draftId: string, occurredAt: string | null) => void;

  // Temporary #245 compatibility bridge. New composer work should resolve
  // restaurant identity without invoking upload until commit semantics are
  // available; this method remains for the old live flow only.
  attachDraftToPlace: (draftId: string, placeId: string) => Promise<void>;

  setDraftCandidate: (draftId: string, candidateId: string, displayName: string) => void;
  resolvePendingCandidates: (userId: string) => Promise<void>;
  deleteDraft: (draftId: string) => Promise<void>;
}

let resolveInFlight = false;

function touchDraft(draft: PostingDraft, patch: Partial<PostingDraft>): PostingDraft {
  return { ...draft, ...patch, updatedAt: Date.now() };
}

function migrateV1State(persistedState: unknown): PersistedDraftStateV1 & { drafts: PostingDraft[] } {
  const state = (persistedState ?? {}) as PersistedDraftStateV1;
  const drafts = Array.isArray(state.drafts)
    ? state.drafts.map((draft): PostingDraft => ({
        ...draft,
        // A V1 candidate draft was logically awaiting promotion even though
        // PR #245 still encoded it as 'pending'. Repair that semantic during
        // migration so the exclusive-claim race fix survives app upgrades.
        outcome:
          draft.restaurantRef.type === 'candidate' && draft.outcome === 'pending'
            ? 'awaiting_place'
            : draft.outcome,
        intent: null,
        reaction: null,
        caption: '',
        visibility: null,
        occurredAt: null,
        updatedAt: draft.createdAt,
      }))
    : [];

  return { ...state, drafts };
}

export const usePostingDraftStore = create<PostingDraftStore>()(
  persist(
    (set, get) => ({
      drafts: [],

      createDraftFromCapture: async ({ ownerId, sourceUri, kind, mimeType, fileSize, intent = null }) => {
        await FileSystem.makeDirectoryAsync(PENDING_DRAFT_MEDIA_DIR, { intermediates: true }).catch(
          () => {}
        );

        const id = generateLocalId();
        const ext = sourceUri.split('.').pop()?.toLowerCase() || (kind === 'photo' ? 'jpg' : 'mp4');
        const destUri = `${PENDING_DRAFT_MEDIA_DIR}${id}.${ext}`;
        await FileSystem.moveAsync({ from: sourceUri, to: destUri });

        const now = Date.now();
        const draft: PostingDraft = {
          id,
          ownerId,
          localUri: destUri,
          kind,
          mimeType,
          fileSize,
          restaurantRef: { type: 'unresolved' },
          intent,
          reaction: null,
          caption: '',
          // Private-log intent has a deterministic privacy floor. Social
          // intent deliberately starts unset so the user must explicitly
          // choose connections/public before commit.
          visibility: intent === 'private_log' ? 'private' : null,
          occurredAt: null,
          outcome: 'pending',
          lastError: null,
          createdAt: now,
          updatedAt: now,
        };

        set({ drafts: [draft, ...get().drafts] });
        return draft;
      },

      setDraftIntent: (draftId, intent) => {
        set({
          drafts: get().drafts.map((draft) => {
            if (draft.id !== draftId) return draft;
            return touchDraft(draft, {
              intent,
              // Private logging is always private. Switching back to social
              // intentionally clears the inherited private visibility so a
              // public/connections audience must be chosen explicitly.
              visibility: intent === 'private_log' ? 'private' : draft.intent === 'private_log' ? null : draft.visibility,
            });
          }),
        });
      },

      setDraftReaction: (draftId, reaction) => {
        set({
          drafts: get().drafts.map((draft) =>
            draft.id === draftId ? touchDraft(draft, { reaction }) : draft
          ),
        });
      },

      setDraftCaption: (draftId, caption) => {
        set({
          drafts: get().drafts.map((draft) =>
            draft.id === draftId ? touchDraft(draft, { caption }) : draft
          ),
        });
      },

      setDraftVisibility: (draftId, visibility) => {
        set({
          drafts: get().drafts.map((draft) => {
            if (draft.id !== draftId) return draft;
            // Frontend state refuses to represent a private log as social.
            // The backend contribution contract must enforce the same rule.
            const nextVisibility = draft.intent === 'private_log' ? 'private' : visibility;
            return touchDraft(draft, { visibility: nextVisibility });
          }),
        });
      },

      setDraftOccurredAt: (draftId, occurredAt) => {
        set({
          drafts: get().drafts.map((draft) =>
            draft.id === draftId ? touchDraft(draft, { occurredAt }) : draft
          ),
        });
      },

      setDraftCandidate: (draftId, candidateId, displayName) => {
        const draft = get().drafts.find((d) => d.id === draftId);
        if (!draft || draft.outcome !== 'pending') return;
        set({
          drafts: get().drafts.map((d) =>
            d.id === draftId
              ? touchDraft(d, {
                  restaurantRef: { type: 'candidate', candidateId, displayName },
                  outcome: 'awaiting_place',
                  lastError: null,
                })
              : d
          ),
        });
      },

      attachDraftToPlace: async (draftId, placeId) => {
        const draft = get().drafts.find((d) => d.id === draftId);
        if (!draft || draft.outcome !== 'pending') return;

        set({
          drafts: get().drafts.map((d) =>
            d.id === draftId
              ? touchDraft(d, {
                  restaurantRef: { type: 'place', placeId },
                  outcome: 'attaching',
                  lastError: null,
                })
              : d
          ),
        });

        try {
          if (draft.kind === 'photo') {
            if (!draft.fileSize) {
              throw new Error("Couldn't read your photo's file size");
            }
            const contentType = resolveImageContentType(draft.mimeType);
            const fileSizeMb = validateUploadSize(draft.fileSize);
            const { image_id, upload_url } = await requestUpload({
              place_id: placeId,
              content_type: contentType,
              file_size_mb: fileSizeMb,
              photo_type: 'food',
            });
            await uploadToSignedUrl(upload_url, draft.localUri, contentType);
            await confirmUpload(image_id);
            await FileSystem.deleteAsync(draft.localUri, { idempotent: true }).catch(() => {});
            useToast.getState().show('Photo submitted for this place');
          } else {
            await useVideoQueueStore.getState().recordVideo({
              sourceUri: draft.localUri,
              placeId,
              contentType: contentTypeForVideoUri(draft.localUri),
              uploadedBy: draft.ownerId,
              templateId: null,
            });
            useToast.getState().show("Saved — it'll post as soon as you're online.");
          }

          set({ drafts: get().drafts.filter((d) => d.id !== draftId) });
        } catch (err) {
          const message = err instanceof Error ? err.message : "Couldn't attach your media to this place";
          set({
            drafts: get().drafts.map((d) =>
              d.id === draftId ? touchDraft(d, { outcome: 'failed', lastError: message }) : d
            ),
          });
          useToast.getState().show(message);
        }
      },

      resolvePendingCandidates: async (userId: string) => {
        if (resolveInFlight) return;
        resolveInFlight = true;
        try {
          const pending = get().drafts.filter(
            (d) =>
              d.ownerId === userId &&
              d.restaurantRef.type === 'candidate' &&
              d.outcome === 'awaiting_place'
          );

          for (const draft of pending) {
            if (draft.restaurantRef.type !== 'candidate') continue;
            try {
              const result = await getCandidateStatus(draft.restaurantRef.candidateId);
              if (result.blocked) {
                set({
                  drafts: get().drafts.map((d) =>
                    d.id === draft.id
                      ? touchDraft(d, {
                          outcome: 'failed',
                          lastError: `${draft.restaurantRef.type === 'candidate' ? draft.restaurantRef.displayName : 'This place'} wasn't added — it didn't get enough corroboration.`,
                        })
                      : d
                  ),
                });
              } else if (result.resolved && result.place_id) {
                // Compatibility bridge: while the old add-spot flow remains
                // live, candidate promotion still attaches immediately. The
                // unified composer migration will replace this with pure
                // restaurant resolution + explicit contribution commit.
                set({
                  drafts: get().drafts.map((d) =>
                    d.id === draft.id ? touchDraft(d, { outcome: 'pending', lastError: null }) : d
                  ),
                });
                await get().attachDraftToPlace(draft.id, result.place_id);
              }
            } catch {
              // Transient status failures leave the durable candidate claim
              // untouched for the next foreground/sign-in resolution pass.
            }
          }
        } finally {
          resolveInFlight = false;
        }
      },

      deleteDraft: async (draftId: string) => {
        const draft = get().drafts.find((d) => d.id === draftId);
        if (!draft) return;
        await FileSystem.deleteAsync(draft.localUri, { idempotent: true }).catch(() => {});
        set({ drafts: get().drafts.filter((d) => d.id !== draftId) });
      },
    }),
    {
      name: 'crave-posting-drafts',
      storage: createJSONStorage(() => AsyncStorage),
      version: PERSIST_VERSION,
      migrate: (persistedState, version) => {
        if (version < PERSIST_VERSION) return migrateV1State(persistedState);
        return persistedState as PostingDraftStore;
      },
    }
  )
);

let _currentUserIdForDraftResolution: string | null = null;

export function setActiveUserForDraftResolution(userId: string | null): void {
  _currentUserIdForDraftResolution = userId;
}

AppState.addEventListener('change', (state) => {
  if (state !== 'active') return;
  if (!_currentUserIdForDraftResolution) return;
  usePostingDraftStore.getState().resolvePendingCandidates(_currentUserIdForDraftResolution).catch(() => {});
});
