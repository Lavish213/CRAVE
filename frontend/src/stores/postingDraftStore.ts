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
import {
  confirmVideoUpload,
  requestVideoUpload,
  uploadVideoToSignedUrl,
  VideoContentType,
} from '../api/videos';
import { createContribution, ContributionOut } from '../api/contributions';
import { getCandidateStatus } from '../api/nearby';
import { useToast } from '../hooks/useToast';

export type DraftMediaKind = 'photo' | 'video';
export type DraftIntent = 'private_log' | 'social_post';
export type DraftReaction = 'loved' | 'good' | 'not_for_me';
export type DraftVisibility = 'private' | 'connections' | 'public';

export type DraftRestaurantRef =
  | { type: 'unresolved' }
  | { type: 'candidate'; candidateId: string; displayName: string }
  | { type: 'place'; placeId: string; displayName?: string };

export type DraftOutcome = 'editing' | 'awaiting_place' | 'committing' | 'failed';

export interface PostingDraft {
  id: string;
  ownerId: string;
  localUri: string | null;
  kind: DraftMediaKind | null;
  mimeType?: string;
  fileSize?: number;
  uploadedMediaId: string | null;
  restaurantRef: DraftRestaurantRef;
  intent: DraftIntent;
  reaction: DraftReaction | null;
  caption: string;
  visibility: DraftVisibility | null;
  occurredAt: string | null;
  outcome: DraftOutcome;
  lastError: string | null;
  createdAt: number;
  updatedAt: number;
}

interface PersistedLegacyDraft {
  id: string;
  ownerId: string;
  localUri?: string | null;
  kind?: DraftMediaKind | null;
  mimeType?: string;
  fileSize?: number;
  restaurantRef?: DraftRestaurantRef;
  outcome?: string;
  lastError?: string | null;
  createdAt?: number;
  intent?: DraftIntent | null;
  reaction?: DraftReaction | null;
  caption?: string;
  visibility?: DraftVisibility | null;
  occurredAt?: string | null;
  updatedAt?: number;
}

interface PersistedLegacyState {
  drafts?: PersistedLegacyDraft[];
}

const PERSIST_VERSION = 3;
const PENDING_DRAFT_MEDIA_DIR = `${FileSystem.documentDirectory}pending_draft_media/`;

function generateLocalId(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function touch(draft: PostingDraft, patch: Partial<PostingDraft>): PostingDraft {
  return { ...draft, ...patch, updatedAt: Date.now() };
}

function resolveImageContentType(mimeType?: string): UploadContentType {
  if (mimeType && (ALLOWED_UPLOAD_TYPES as readonly string[]).includes(mimeType)) {
    return mimeType as UploadContentType;
  }
  return 'image/jpeg';
}

function videoContentType(uri: string, mimeType?: string): VideoContentType {
  if (mimeType === 'video/quicktime' || mimeType === 'video/webm' || mimeType === 'video/mp4') {
    return mimeType;
  }
  const ext = uri.split('.').pop()?.toLowerCase();
  if (ext === 'mov') return 'video/quicktime';
  if (ext === 'webm') return 'video/webm';
  return 'video/mp4';
}

function migrateState(state: unknown): PersistedLegacyState & { drafts: PostingDraft[] } {
  const legacy = (state ?? {}) as PersistedLegacyState;
  const now = Date.now();
  return {
    ...legacy,
    drafts: Array.isArray(legacy.drafts)
      ? legacy.drafts.map((draft) => {
          const createdAt = draft.createdAt ?? now;
          const intent = draft.intent ?? 'social_post';
          const candidate = draft.restaurantRef?.type === 'candidate';
          return {
            id: draft.id,
            ownerId: draft.ownerId,
            localUri: draft.localUri ?? null,
            kind: draft.kind ?? null,
            mimeType: draft.mimeType,
            fileSize: draft.fileSize,
            uploadedMediaId: null,
            restaurantRef: draft.restaurantRef ?? { type: 'unresolved' },
            intent,
            reaction: draft.reaction ?? null,
            caption: draft.caption ?? '',
            visibility: intent === 'private_log' ? 'private' : draft.visibility ?? null,
            occurredAt: draft.occurredAt ?? null,
            outcome: candidate ? 'awaiting_place' : 'editing',
            lastError: draft.lastError ?? null,
            createdAt,
            updatedAt: draft.updatedAt ?? createdAt,
          } satisfies PostingDraft;
        })
      : [],
  };
}

interface PostingDraftStore {
  drafts: PostingDraft[];
  createDraft: (ownerId: string, intent: DraftIntent) => PostingDraft;
  createDraftFromCapture: (opts: {
    ownerId: string;
    sourceUri: string;
    kind: DraftMediaKind;
    mimeType?: string;
    fileSize?: number;
    intent?: DraftIntent;
  }) => Promise<PostingDraft>;
  addMediaToDraft: (draftId: string, opts: {
    sourceUri: string;
    kind: DraftMediaKind;
    mimeType?: string;
    fileSize?: number;
  }) => Promise<void>;
  setDraftPlace: (draftId: string, placeId: string, displayName?: string) => void;
  setDraftCandidate: (draftId: string, candidateId: string, displayName: string) => void;
  setDraftIntent: (draftId: string, intent: DraftIntent) => void;
  setDraftReaction: (draftId: string, reaction: DraftReaction | null) => void;
  setDraftCaption: (draftId: string, caption: string) => void;
  setDraftVisibility: (draftId: string, visibility: DraftVisibility) => void;
  setDraftOccurredAt: (draftId: string, occurredAt: string | null) => void;
  resolvePendingCandidates: (userId: string) => Promise<void>;
  commitDraft: (draftId: string) => Promise<ContributionOut | null>;
  deleteDraft: (draftId: string) => Promise<void>;
}

let resolveInFlight = false;

export const usePostingDraftStore = create<PostingDraftStore>()(
  persist(
    (set, get) => ({
      drafts: [],

      createDraft: (ownerId, intent) => {
        const now = Date.now();
        const draft: PostingDraft = {
          id: generateLocalId(),
          ownerId,
          localUri: null,
          kind: null,
          uploadedMediaId: null,
          restaurantRef: { type: 'unresolved' },
          intent,
          reaction: null,
          caption: '',
          visibility: intent === 'private_log' ? 'private' : null,
          occurredAt: null,
          outcome: 'editing',
          lastError: null,
          createdAt: now,
          updatedAt: now,
        };
        set({ drafts: [draft, ...get().drafts] });
        return draft;
      },

      createDraftFromCapture: async ({ ownerId, sourceUri, kind, mimeType, fileSize, intent = 'social_post' }) => {
        const draft = get().createDraft(ownerId, intent);
        await get().addMediaToDraft(draft.id, { sourceUri, kind, mimeType, fileSize });
        return get().drafts.find((item) => item.id === draft.id) ?? draft;
      },

      addMediaToDraft: async (draftId, { sourceUri, kind, mimeType, fileSize }) => {
        const draft = get().drafts.find((item) => item.id === draftId);
        if (!draft || draft.outcome === 'committing') return;
        await FileSystem.makeDirectoryAsync(PENDING_DRAFT_MEDIA_DIR, { intermediates: true }).catch(() => {});
        const ext = sourceUri.split('.').pop()?.toLowerCase() || (kind === 'photo' ? 'jpg' : 'mp4');
        const destUri = `${PENDING_DRAFT_MEDIA_DIR}${draftId}-${Date.now()}.${ext}`;
        await FileSystem.moveAsync({ from: sourceUri, to: destUri });
        if (draft.localUri) {
          await FileSystem.deleteAsync(draft.localUri, { idempotent: true }).catch(() => {});
        }
        set({
          drafts: get().drafts.map((item) =>
            item.id === draftId
              ? touch(item, {
                  localUri: destUri,
                  kind,
                  mimeType,
                  fileSize,
                  uploadedMediaId: null,
                  outcome: 'editing',
                  lastError: null,
                })
              : item
          ),
        });
      },

      setDraftPlace: (draftId, placeId, displayName) => {
        set({
          drafts: get().drafts.map((draft) =>
            draft.id === draftId
              ? touch(draft, {
                  restaurantRef: { type: 'place', placeId, displayName },
                  outcome: 'editing',
                  lastError: null,
                })
              : draft
          ),
        });
      },

      setDraftCandidate: (draftId, candidateId, displayName) => {
        set({
          drafts: get().drafts.map((draft) =>
            draft.id === draftId && draft.outcome !== 'committing'
              ? touch(draft, {
                  restaurantRef: { type: 'candidate', candidateId, displayName },
                  outcome: 'awaiting_place',
                  lastError: null,
                })
              : draft
          ),
        });
      },

      setDraftIntent: (draftId, intent) => {
        set({
          drafts: get().drafts.map((draft) =>
            draft.id === draftId
              ? touch(draft, {
                  intent,
                  visibility: intent === 'private_log' ? 'private' : draft.intent === 'private_log' ? null : draft.visibility,
                })
              : draft
          ),
        });
      },

      setDraftReaction: (draftId, reaction) => {
        set({ drafts: get().drafts.map((draft) => draft.id === draftId ? touch(draft, { reaction }) : draft) });
      },

      setDraftCaption: (draftId, caption) => {
        set({ drafts: get().drafts.map((draft) => draft.id === draftId ? touch(draft, { caption }) : draft) });
      },

      setDraftVisibility: (draftId, visibility) => {
        set({
          drafts: get().drafts.map((draft) =>
            draft.id === draftId
              ? touch(draft, { visibility: draft.intent === 'private_log' ? 'private' : visibility })
              : draft
          ),
        });
      },

      setDraftOccurredAt: (draftId, occurredAt) => {
        set({ drafts: get().drafts.map((draft) => draft.id === draftId ? touch(draft, { occurredAt }) : draft) });
      },

      resolvePendingCandidates: async (userId) => {
        if (resolveInFlight) return;
        resolveInFlight = true;
        try {
          const pending = get().drafts.filter(
            (draft) => draft.ownerId === userId && draft.restaurantRef.type === 'candidate' && draft.outcome === 'awaiting_place'
          );
          for (const draft of pending) {
            if (draft.restaurantRef.type !== 'candidate') continue;
            try {
              const result = await getCandidateStatus(draft.restaurantRef.candidateId);
              if (result.resolved && result.place_id) {
                get().setDraftPlace(draft.id, result.place_id, draft.restaurantRef.displayName);
              } else if (result.blocked) {
                set({
                  drafts: get().drafts.map((item) =>
                    item.id === draft.id
                      ? touch(item, {
                          restaurantRef: { type: 'unresolved' },
                          outcome: 'failed',
                          lastError: `${draft.restaurantRef.type === 'candidate' ? draft.restaurantRef.displayName : 'This place'} wasn't confirmed. Choose another restaurant when you're ready.`,
                        })
                      : item
                  ),
                });
              }
            } catch {
              // A transient lookup failure leaves the durable candidate reference intact.
            }
          }
        } finally {
          resolveInFlight = false;
        }
      },

      commitDraft: async (draftId) => {
        const initial = get().drafts.find((draft) => draft.id === draftId);
        if (!initial) return null;
        if (initial.restaurantRef.type !== 'place') {
          const message = initial.restaurantRef.type === 'candidate'
            ? "We're still verifying this restaurant. Your draft is safe."
            : 'Choose a restaurant before finishing.';
          useToast.getState().show(message);
          return null;
        }
        if (initial.intent === 'social_post' && initial.visibility !== 'connections' && initial.visibility !== 'public') {
          useToast.getState().show('Choose who can see this before posting.');
          return null;
        }
        if (initial.intent === 'social_post' && (!initial.localUri || !initial.kind)) {
          useToast.getState().show('Add a photo or video before sharing.');
          return null;
        }

        set({
          drafts: get().drafts.map((draft) =>
            draft.id === draftId ? touch(draft, { outcome: 'committing', lastError: null }) : draft
          ),
        });

        try {
          let current = get().drafts.find((draft) => draft.id === draftId) ?? initial;
          let imageId: string | null = current.kind === 'photo' ? current.uploadedMediaId : null;
          let videoId: string | null = current.kind === 'video' ? current.uploadedMediaId : null;

          if (current.localUri && current.kind && !current.uploadedMediaId) {
            if (current.kind === 'photo') {
              if (!current.fileSize) throw new Error("Couldn't read your photo's file size");
              const contentType = resolveImageContentType(current.mimeType);
              const { image_id, upload_url } = await requestUpload({
                place_id: current.restaurantRef.type === 'place' ? current.restaurantRef.placeId : initial.restaurantRef.placeId,
                content_type: contentType,
                file_size_mb: validateUploadSize(current.fileSize),
                photo_type: 'food',
              });
              await uploadToSignedUrl(upload_url, current.localUri, contentType);
              await confirmUpload(image_id);
              imageId = image_id;
            } else {
              const contentType = videoContentType(current.localUri, current.mimeType);
              const { video_id, upload_url } = await requestVideoUpload({
                place_id: current.restaurantRef.type === 'place' ? current.restaurantRef.placeId : initial.restaurantRef.placeId,
                content_type: contentType,
                client_id: current.id,
              });
              await uploadVideoToSignedUrl(upload_url, current.localUri, contentType);
              await confirmVideoUpload(video_id);
              videoId = video_id;
            }
            const serverId = imageId ?? videoId;
            set({
              drafts: get().drafts.map((draft) =>
                draft.id === draftId && serverId ? touch(draft, { uploadedMediaId: serverId }) : draft
              ),
            });
            current = get().drafts.find((draft) => draft.id === draftId) ?? current;
          }

          const placeId = initial.restaurantRef.placeId;
          const contribution = await createContribution({
            client_id: current.id,
            place_id: placeId,
            intent: current.intent,
            reaction: current.reaction,
            caption: current.caption.trim() || null,
            visibility: current.intent === 'private_log' ? 'private' : current.visibility ?? 'private',
            occurred_at: current.occurredAt,
            image_id: imageId,
            video_id: videoId,
          });

          if (current.localUri) {
            await FileSystem.deleteAsync(current.localUri, { idempotent: true }).catch(() => {});
          }
          set({ drafts: get().drafts.filter((draft) => draft.id !== draftId) });
          useToast.getState().show(current.intent === 'private_log' ? 'Saved privately' : 'Food find posted');
          return contribution;
        } catch (error) {
          const message = error instanceof Error ? error.message : "Couldn't finish this yet. Your draft is safe.";
          set({
            drafts: get().drafts.map((draft) =>
              draft.id === draftId ? touch(draft, { outcome: 'failed', lastError: message }) : draft
            ),
          });
          useToast.getState().show(message);
          return null;
        }
      },

      deleteDraft: async (draftId) => {
        const draft = get().drafts.find((item) => item.id === draftId);
        if (!draft || draft.outcome === 'committing') return;
        if (draft.localUri) {
          await FileSystem.deleteAsync(draft.localUri, { idempotent: true }).catch(() => {});
        }
        set({ drafts: get().drafts.filter((item) => item.id !== draftId) });
      },
    }),
    {
      name: 'crave-posting-drafts',
      storage: createJSONStorage(() => AsyncStorage),
      version: PERSIST_VERSION,
      migrate: migrateState,
    }
  )
);

let activeUserId: string | null = null;

export function setActiveUserForDraftResolution(userId: string | null): void {
  activeUserId = userId;
}

AppState.addEventListener('change', (state) => {
  if (state !== 'active' || !activeUserId) return;
  usePostingDraftStore.getState().resolvePendingCandidates(activeUserId).catch(() => {});
});
