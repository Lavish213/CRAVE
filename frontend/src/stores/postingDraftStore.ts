import { AppState } from 'react-native';
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as FileSystem from 'expo-file-system/legacy';

import { getCandidateStatus } from '../api/nearby';

export type DraftMediaKind = 'photo' | 'video';
export type DraftIntent = 'private_log' | 'social_post';
export type DraftReaction = 'loved' | 'good' | 'not_for_me';
export type DraftVisibility = 'private' | 'connections' | 'public';
export type DraftRestaurantRef =
  | { type: 'unresolved' }
  | { type: 'candidate'; candidateId: string; displayName: string }
  | { type: 'place'; placeId: string };
export type DraftOutcome = 'pending' | 'awaiting_place' | 'failed';

export interface PostingDraft {
  id: string;
  ownerId: string;
  localUri: string;
  kind: DraftMediaKind;
  mimeType?: string;
  fileSize?: number;
  restaurantRef: DraftRestaurantRef;
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
interface PersistedDraftStateV1 { drafts?: PostingDraftV1[] }

const PERSIST_VERSION = 3;
const PENDING_DRAFT_MEDIA_DIR = `${FileSystem.documentDirectory}pending_draft_media/`;
let resolveInFlight = false;

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

interface PostingDraftStore {
  drafts: PostingDraft[];
  createDraftFromCapture: (opts: {
    ownerId: string; sourceUri: string; kind: DraftMediaKind; mimeType?: string; fileSize?: number; intent?: DraftIntent | null;
  }) => Promise<PostingDraft>;
  setDraftPlace: (draftId: string, placeId: string) => void;
  setDraftCandidate: (draftId: string, candidateId: string, displayName: string) => void;
  setDraftIntent: (draftId: string, intent: DraftIntent) => void;
  setDraftReaction: (draftId: string, reaction: DraftReaction | null) => void;
  setDraftCaption: (draftId: string, caption: string) => void;
  setDraftVisibility: (draftId: string, visibility: DraftVisibility) => void;
  setDraftOccurredAt: (draftId: string, occurredAt: string | null) => void;
  resolvePendingCandidates: (userId: string) => Promise<void>;
  deleteDraft: (draftId: string) => Promise<void>;
}

export const usePostingDraftStore = create<PostingDraftStore>()(
  persist(
    (set, get) => ({
      drafts: [],
      createDraftFromCapture: async ({ ownerId, sourceUri, kind, mimeType, fileSize, intent = null }) => {
        await FileSystem.makeDirectoryAsync(PENDING_DRAFT_MEDIA_DIR, { intermediates: true }).catch(() => {});
        const id = generateLocalId();
        const ext = sourceUri.split('.').pop()?.toLowerCase() || (kind === 'photo' ? 'jpg' : 'mp4');
        const localUri = `${PENDING_DRAFT_MEDIA_DIR}${id}.${ext}`;
        await FileSystem.moveAsync({ from: sourceUri, to: localUri });
        const now = Date.now();
        const draft: PostingDraft = {
          id, ownerId, localUri, kind, mimeType, fileSize,
          restaurantRef: { type: 'unresolved' }, intent, reaction: null, caption: '',
          visibility: intent === 'private_log' ? 'private' : null,
          occurredAt: null, outcome: 'pending', lastError: null, createdAt: now, updatedAt: now,
        };
        set({ drafts: [draft, ...get().drafts] });
        return draft;
      },
      setDraftPlace: (draftId, placeId) => set({ drafts: get().drafts.map((d) => d.id === draftId ? touch(d, { restaurantRef: { type: 'place', placeId }, outcome: 'pending', lastError: null }) : d) }),
      setDraftCandidate: (draftId, candidateId, displayName) => set({ drafts: get().drafts.map((d) => d.id === draftId ? touch(d, { restaurantRef: { type: 'candidate', candidateId, displayName }, outcome: 'awaiting_place', lastError: null }) : d) }),
      setDraftIntent: (draftId, intent) => set({ drafts: get().drafts.map((d) => d.id === draftId ? touch(d, { intent, visibility: intent === 'private_log' ? 'private' : d.intent === 'private_log' ? null : d.visibility }) : d) }),
      setDraftReaction: (draftId, reaction) => set({ drafts: get().drafts.map((d) => d.id === draftId ? touch(d, { reaction }) : d) }),
      setDraftCaption: (draftId, caption) => set({ drafts: get().drafts.map((d) => d.id === draftId ? touch(d, { caption }) : d) }),
      setDraftVisibility: (draftId, visibility) => set({ drafts: get().drafts.map((d) => d.id === draftId ? touch(d, { visibility: d.intent === 'private_log' ? 'private' : visibility }) : d) }),
      setDraftOccurredAt: (draftId, occurredAt) => set({ drafts: get().drafts.map((d) => d.id === draftId ? touch(d, { occurredAt }) : d) }),
      resolvePendingCandidates: async (userId) => {
        if (resolveInFlight) return;
        resolveInFlight = true;
        try {
          const pending = get().drafts.filter((d) => d.ownerId === userId && d.restaurantRef.type === 'candidate' && d.outcome === 'awaiting_place');
          for (const draft of pending) {
            if (draft.restaurantRef.type !== 'candidate') continue;
            try {
              const result = await getCandidateStatus(draft.restaurantRef.candidateId);
              if (result.blocked) {
                set({ drafts: get().drafts.map((d) => d.id === draft.id ? touch(d, { outcome: 'failed', lastError: `${draft.restaurantRef.type === 'candidate' ? draft.restaurantRef.displayName : 'This place'} wasn't added — it didn't get enough corroboration.` }) : d) });
              } else if (result.resolved && result.place_id) {
                get().setDraftPlace(draft.id, result.place_id);
              }
            } catch { /* transient: keep durable draft unchanged */ }
          }
        } finally { resolveInFlight = false; }
      },
      deleteDraft: async (draftId) => {
        const draft = get().drafts.find((d) => d.id === draftId);
        if (!draft) return;
        await FileSystem.deleteAsync(draft.localUri, { idempotent: true }).catch(() => {});
        set({ drafts: get().drafts.filter((d) => d.id !== draftId) });
      },
    }),
    {
      name: 'crave-posting-drafts', storage: createJSONStorage(() => AsyncStorage), version: PERSIST_VERSION,
      migrate: (state, version) => {
        if (version >= 2) return state as PostingDraftStore;
        const old = (state ?? {}) as PersistedDraftStateV1;
        return {
          ...old,
          drafts: (old.drafts ?? []).filter((d) => d.outcome !== 'attached').map((d): PostingDraft => ({
            ...d,
            outcome: d.restaurantRef.type === 'candidate' ? 'awaiting_place' : d.outcome === 'failed' ? 'failed' : 'pending',
            intent: null, reaction: null, caption: '', visibility: null, occurredAt: null, updatedAt: d.createdAt,
          })),
        } as unknown as PostingDraftStore;
      },
    }
  )
);

let activeUserId: string | null = null;
export function setActiveUserForDraftResolution(userId: string | null): void { activeUserId = userId; }
AppState.addEventListener('change', (state) => {
  if (state === 'active' && activeUserId) usePostingDraftStore.getState().resolvePendingCandidates(activeUserId).catch(() => {});
});
