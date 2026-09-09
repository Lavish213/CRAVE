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
export type DraftRestaurantRef = { type: 'unresolved' } | { type: 'candidate'; candidateId: string; displayName: string } | { type: 'place'; placeId: string };
export type DraftOutcome = 'pending' | 'awaiting_place' | 'failed';

export interface PostingDraft {
  id: string; ownerId: string; localUri: string; kind: DraftMediaKind; mimeType?: string; fileSize?: number;
  restaurantRef: DraftRestaurantRef; intent: DraftIntent | null; reaction: DraftReaction | null; caption: string;
  visibility: DraftVisibility | null; occurredAt: string | null; uploadedMediaId: string | null;
  outcome: DraftOutcome; lastError: string | null; createdAt: number; updatedAt: number;
}

type LegacyDraft = Partial<PostingDraft> & { id: string; ownerId: string; localUri: string; kind: DraftMediaKind; restaurantRef: DraftRestaurantRef; createdAt: number; outcome?: string };
type PersistedLegacyState = { drafts?: LegacyDraft[] };
const PERSIST_VERSION = 3;
const PENDING_DRAFT_MEDIA_DIR = `${FileSystem.documentDirectory}pending_draft_media/`;
let resolveInFlight = false;

function generateLocalId(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0; const v = c === 'x' ? r : (r & 0x3) | 0x8; return v.toString(16);
  });
}
function touch(draft: PostingDraft, patch: Partial<PostingDraft>): PostingDraft { return { ...draft, ...patch, updatedAt: Date.now() }; }

interface PostingDraftStore {
  drafts: PostingDraft[];
  createDraftFromCapture: (opts: { ownerId: string; sourceUri: string; kind: DraftMediaKind; mimeType?: string; fileSize?: number; intent?: DraftIntent | null }) => Promise<PostingDraft>;
  setDraftPlace: (draftId: string, placeId: string) => void;
  attachDraftToPlace: (draftId: string, placeId: string) => Promise<void>;
  setDraftCandidate: (draftId: string, candidateId: string, displayName: string) => void;
  setDraftIntent: (draftId: string, intent: DraftIntent) => void;
  setDraftReaction: (draftId: string, reaction: DraftReaction | null) => void;
  setDraftCaption: (draftId: string, caption: string) => void;
  setDraftVisibility: (draftId: string, visibility: DraftVisibility) => void;
  setDraftOccurredAt: (draftId: string, occurredAt: string | null) => void;
  setUploadedMediaId: (draftId: string, mediaId: string) => void;
  resolvePendingCandidates: (userId: string) => Promise<void>;
  deleteDraft: (draftId: string) => Promise<void>;
}

export const usePostingDraftStore = create<PostingDraftStore>()(
  persist(
    (set, get) => ({
      drafts: [],
      createDraftFromCapture: async ({ ownerId, sourceUri, kind, mimeType, fileSize, intent = null }) => {
        await FileSystem.makeDirectoryAsync(PENDING_DRAFT_MEDIA_DIR, { intermediates: true }).catch(() => {});
        const id = generateLocalId(); const ext = sourceUri.split('.').pop()?.toLowerCase() || (kind === 'photo' ? 'jpg' : 'mp4');
        const localUri = `${PENDING_DRAFT_MEDIA_DIR}${id}.${ext}`; await FileSystem.moveAsync({ from: sourceUri, to: localUri });
        const now = Date.now();
        const draft: PostingDraft = { id, ownerId, localUri, kind, mimeType, fileSize, restaurantRef: { type: 'unresolved' }, intent, reaction: null, caption: '', visibility: intent === 'private_log' ? 'private' : null, occurredAt: null, uploadedMediaId: null, outcome: 'pending', lastError: null, createdAt: now, updatedAt: now };
        set({ drafts: [draft, ...get().drafts] }); return draft;
      },
      setDraftPlace: (id, placeId) => set({ drafts: get().drafts.map((d) => d.id === id ? touch(d, { restaurantRef: { type: 'place', placeId }, outcome: 'pending', lastError: null }) : d) }),
      // Temporary source-compatibility alias for legacy add-spot callers.
      // It now resolves identity only; it never uploads or destroys media.
      attachDraftToPlace: async (id, placeId) => { get().setDraftPlace(id, placeId); },
      setDraftCandidate: (id, candidateId, displayName) => set({ drafts: get().drafts.map((d) => d.id === id ? touch(d, { restaurantRef: { type: 'candidate', candidateId, displayName }, outcome: 'awaiting_place', lastError: null }) : d) }),
      setDraftIntent: (id, intent) => set({ drafts: get().drafts.map((d) => d.id === id ? touch(d, { intent, visibility: intent === 'private_log' ? 'private' : d.intent === 'private_log' ? null : d.visibility }) : d) }),
      setDraftReaction: (id, reaction) => set({ drafts: get().drafts.map((d) => d.id === id ? touch(d, { reaction }) : d) }),
      setDraftCaption: (id, caption) => set({ drafts: get().drafts.map((d) => d.id === id ? touch(d, { caption }) : d) }),
      setDraftVisibility: (id, visibility) => set({ drafts: get().drafts.map((d) => d.id === id ? touch(d, { visibility: d.intent === 'private_log' ? 'private' : visibility }) : d) }),
      setDraftOccurredAt: (id, occurredAt) => set({ drafts: get().drafts.map((d) => d.id === id ? touch(d, { occurredAt }) : d) }),
      setUploadedMediaId: (id, uploadedMediaId) => set({ drafts: get().drafts.map((d) => d.id === id ? touch(d, { uploadedMediaId }) : d) }),
      resolvePendingCandidates: async (userId) => {
        if (resolveInFlight) return; resolveInFlight = true;
        try {
          for (const draft of get().drafts.filter((d) => d.ownerId === userId && d.restaurantRef.type === 'candidate' && d.outcome === 'awaiting_place')) {
            if (draft.restaurantRef.type !== 'candidate') continue;
            try {
              const result = await getCandidateStatus(draft.restaurantRef.candidateId);
              if (result.blocked) set({ drafts: get().drafts.map((d) => d.id === draft.id ? touch(d, { outcome: 'failed', lastError: `${draft.restaurantRef.type === 'candidate' ? draft.restaurantRef.displayName : 'This place'} wasn't added — it didn't get enough corroboration.` }) : d) });
              else if (result.resolved && result.place_id) get().setDraftPlace(draft.id, result.place_id);
            } catch { /* keep durable state */ }
          }
        } finally { resolveInFlight = false; }
      },
      deleteDraft: async (id) => {
        const draft = get().drafts.find((d) => d.id === id); if (!draft) return;
        await FileSystem.deleteAsync(draft.localUri, { idempotent: true }).catch(() => {});
        set({ drafts: get().drafts.filter((d) => d.id !== id) });
      },
    }),
    {
      name: 'crave-posting-drafts', storage: createJSONStorage(() => AsyncStorage), version: PERSIST_VERSION,
      migrate: (state, version) => {
        if (version >= PERSIST_VERSION) return state as PostingDraftStore;
        const legacy = (state ?? {}) as PersistedLegacyState;
        return {
          ...legacy,
          drafts: (legacy.drafts ?? []).filter((d) => d.outcome !== 'attached').map((d): PostingDraft => ({
            id: d.id, ownerId: d.ownerId, localUri: d.localUri, kind: d.kind, mimeType: d.mimeType, fileSize: d.fileSize,
            restaurantRef: d.restaurantRef, intent: d.intent ?? null, reaction: d.reaction ?? null, caption: d.caption ?? '',
            visibility: d.intent === 'private_log' ? 'private' : d.visibility ?? null, occurredAt: d.occurredAt ?? null, uploadedMediaId: null,
            outcome: d.restaurantRef.type === 'candidate' ? 'awaiting_place' : d.outcome === 'failed' ? 'failed' : 'pending',
            lastError: d.lastError ?? null, createdAt: d.createdAt, updatedAt: d.updatedAt ?? d.createdAt,
          })),
        } as unknown as PostingDraftStore;
      },
    }
  )
);

let activeUserId: string | null = null;
export function setActiveUserForDraftResolution(userId: string | null): void { activeUserId = userId; }
AppState.addEventListener('change', (state) => { if (state === 'active' && activeUserId) usePostingDraftStore.getState().resolvePendingCandidates(activeUserId).catch(() => {}); });
