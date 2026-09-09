// postingDraftStore.ts
//
// Posting V2-A: a photo/video captured in food-evidence.tsx must survive
// however long it takes to identify the restaurant, including the case
// where the restaurant doesn't exist in CRAVE yet at all. Mirrors
// videoQueueStore.ts's local-file-first pattern (move the captured media
// into an app-owned directory immediately, before any network call) --
// but starts *before* a restaurant is even known, which videoQueueStore's
// recordVideo can't do (it requires a placeId up front). That's exactly
// why a missing/unidentified restaurant used to mean losing the captured
// media (see PR #238, which fixed the already-in-CRAVE case only and
// deliberately deferred this one as "Option B").
//
// A draft's restaurantRef moves through three states:
//   unresolved -- captured, no restaurant identified yet
//   candidate  -- user identified a place CRAVE doesn't have yet;
//                 confirmNewSpot() was called, corroboration/promotion is
//                 async and may take a while (or never happen)
//   place      -- a real place_id exists, media can attach now
//
// Attaching to a place reuses existing, already-correct machinery rather
// than duplicating it: video hands off to videoQueueStore.recordVideo()
// (which itself re-persists the file into its own durable queue and owns
// upload/retry from there); photo calls the same plain request/PUT/confirm
// sequence useUploadImage.ts already uses (imported directly here, not via
// that hook, since store code isn't a React component).
import { AppState } from 'react-native';
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
// See videoQueueStore.ts's identical comment -- SDK54 moved expo-file-
// system's promise-based API to this /legacy subpath, still fully
// supported.
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
  outcome: DraftOutcome;
  lastError: string | null;
  createdAt: number;
}

function resolveImageContentType(mimeType?: string): UploadContentType {
  if (mimeType && (ALLOWED_UPLOAD_TYPES as readonly string[]).includes(mimeType)) {
    return mimeType as UploadContentType;
  }
  return 'image/jpeg';
}

// Mirrors record-video/[placeId].tsx's identical helper.
function contentTypeForVideoUri(uri: string): 'video/mp4' | 'video/quicktime' | 'video/webm' {
  const ext = uri.split('.').pop()?.toLowerCase();
  if (ext === 'mov') return 'video/quicktime';
  if (ext === 'webm') return 'video/webm';
  return 'video/mp4';
}

// Same non-cryptographic local-id generator as videoQueueStore.ts -- purely
// a client-side key, never a security boundary.
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

  // Step 1: durable local copy, no network, no restaurant needed yet.
  createDraftFromCapture: (opts: {
    ownerId: string;
    sourceUri: string;
    kind: DraftMediaKind;
    mimeType?: string;
    fileSize?: number;
  }) => Promise<PostingDraft>;

  // User identified an existing CRAVE place -- attach now.
  attachDraftToPlace: (draftId: string, placeId: string) => Promise<void>;

  // User identified a place CRAVE doesn't have yet -- confirmNewSpot()
  // already ran; this records the reference and *claims* the draft for
  // candidate resolution so a later/rapid existing-place tap cannot attach
  // the same media somewhere else while promotion is pending.
  setDraftCandidate: (draftId: string, candidateId: string, displayName: string) => void;

  // Check every candidate-ref draft owned by userId against the backend;
  // auto-attach any that have been promoted to a place.
  resolvePendingCandidates: (userId: string) => Promise<void>;

  deleteDraft: (draftId: string) => Promise<void>;
}

let resolveInFlight = false;

export const usePostingDraftStore = create<PostingDraftStore>()(
  persist(
    (set, get) => ({
      drafts: [],

      createDraftFromCapture: async ({ ownerId, sourceUri, kind, mimeType, fileSize }) => {
        await FileSystem.makeDirectoryAsync(PENDING_DRAFT_MEDIA_DIR, { intermediates: true }).catch(
          () => {}
        );

        const id = generateLocalId();
        const ext = sourceUri.split('.').pop()?.toLowerCase() || (kind === 'photo' ? 'jpg' : 'mp4');
        const destUri = `${PENDING_DRAFT_MEDIA_DIR}${id}.${ext}`;
        await FileSystem.moveAsync({ from: sourceUri, to: destUri });

        const draft: PostingDraft = {
          id,
          ownerId,
          localUri: destUri,
          kind,
          mimeType,
          fileSize,
          restaurantRef: { type: 'unresolved' },
          outcome: 'pending',
          lastError: null,
          createdAt: Date.now(),
        };

        set({ drafts: [draft, ...get().drafts] });
        return draft;
      },

      setDraftCandidate: (draftId, candidateId, displayName) => {
        // Claim synchronously. `restaurantRef` alone is not a lock: leaving
        // outcome='pending' here allowed a rapid existing-place action to
        // enter attachDraftToPlace afterward and reassign/upload this same
        // media to a different restaurant. `awaiting_place` is both the
        // truthful lifecycle state and the exclusive claim while the
        // DiscoveryCandidate is waiting for promotion.
        const draft = get().drafts.find((d) => d.id === draftId);
        if (!draft || draft.outcome !== 'pending') return;
        set({
          drafts: get().drafts.map((d) =>
            d.id === draftId
              ? {
                  ...d,
                  restaurantRef: { type: 'candidate', candidateId, displayName },
                  outcome: 'awaiting_place',
                  lastError: null,
                }
              : d
          ),
        });
      },

      attachDraftToPlace: async (draftId, placeId) => {
        const draft = get().drafts.find((d) => d.id === draftId);
        // 'pending' only. Candidate selection moves the draft to
        // 'awaiting_place', so direct existing-place attachment cannot race
        // with a candidate claim. Candidate resolution temporarily restores
        // 'pending' and immediately invokes this function in the same JS
        // turn; this function synchronously flips to 'attaching' before its
        // first await, preserving exclusivity.
        if (!draft || draft.outcome !== 'pending') return;

        set({
          drafts: get().drafts.map((d) =>
            d.id === draftId
              ? { ...d, restaurantRef: { type: 'place', placeId }, outcome: 'attaching', lastError: null }
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
            // Hands off to videoQueueStore's own durable queue/upload --
            // it re-persists the file into its own directory and owns
            // retry from here, so this draft's job ends the moment the
            // hand-off succeeds.
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
              d.id === draftId ? { ...d, outcome: 'failed', lastError: message } : d
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
            if (draft.restaurantRef.type !== 'candidate') continue; // narrows for TS
            try {
              const result = await getCandidateStatus(draft.restaurantRef.candidateId);
              if (result.blocked) {
                set({
                  drafts: get().drafts.map((d) =>
                    d.id === draft.id
                      ? {
                          ...d,
                          outcome: 'failed',
                          lastError: `${draft.restaurantRef.type === 'candidate' ? draft.restaurantRef.displayName : 'This place'} wasn't added — it didn't get enough corroboration.`,
                        }
                      : d
                  ),
                });
              } else if (result.resolved && result.place_id) {
                // Release only to the resolved attachment path, then invoke
                // it immediately. attachDraftToPlace synchronously flips the
                // draft to 'attaching' before any await, so no UI action can
                // interleave and steal the claim in this JS turn.
                set({
                  drafts: get().drafts.map((d) =>
                    d.id === draft.id ? { ...d, outcome: 'pending', lastError: null } : d
                  ),
                });
                await get().attachDraftToPlace(draft.id, result.place_id);
              }
              // Neither resolved nor blocked yet -- stays awaiting_place,
              // check again next foreground.
            } catch {
              // A transient failure checking status shouldn't mark the
              // draft failed -- the media and the candidate reference are
              // both still perfectly fine, just try again next time.
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
    }
  )
);

// Foreground trigger -- mirrors videoQueueStore.ts's identical listener.
// Callers still need to invoke resolvePendingCandidates(userId) themselves
// once on mount/sign-in; this only covers "the app was already showing a
// signed-in user and came back to the foreground."
let _currentUserIdForDraftResolution: string | null = null;

export function setActiveUserForDraftResolution(userId: string | null): void {
  _currentUserIdForDraftResolution = userId;
}

AppState.addEventListener('change', (state) => {
  if (state !== 'active') return;
  if (!_currentUserIdForDraftResolution) return;
  usePostingDraftStore.getState().resolvePendingCandidates(_currentUserIdForDraftResolution).catch(() => {});
});
