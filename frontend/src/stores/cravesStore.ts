// Renamed from hitlistStore.ts — the user-facing feature is Craves/Saves.
import { AppState } from 'react-native';
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { PlaceOut } from '../api/places';
import {
  fetchSaves,
  createSave,
  deleteSave,
  updateSaveMemory,
  SavedPlace,
  SaveMemoryUpdate,
} from '../api/saves';
import { logRecommendationEvent } from '../utils/recommendationEventQueue';
import { RecommendationSurface } from '../api/recommendationEvents';

export interface SaveEventMeta {
  surface?: RecommendationSurface;
  position?: number | null;
  rank_percentile?: number | null;
  city_id?: string | null;
  query?: string | null;
}

export interface PendingSyncAction {
  type: 'add' | 'remove';
  userId: string;
  queuedAt: number;
  attemptCount: number;
  lastAttemptAt: number | null;
  meta?: SaveEventMeta;
  /** Stable idempotency key for the eventual confirmed Ledger outcome. */
  eventId?: string;
}

interface CravesStore {
  saves: SavedPlace[];
  loading: boolean;
  error: string | null;
  /** Account that owns the cached `saves` array. */
  savesUserId: string | null;
  /** Account-owned offline save/remove debts. Kept across sign-out/restart. */
  pendingSyncActions: Record<string, PendingSyncAction>;

  loadSaves: (userId: string) => Promise<void>;
  addSave: (place: PlaceOut, userId: string, meta?: SaveEventMeta) => Promise<string | null>;
  removeSave: (placeId: string, userId: string, meta?: SaveEventMeta) => Promise<string | null>;
  clearSaves: () => void;
  isSaved: (placeId: string) => boolean;
  setSaveMemory: (placeId: string, updates: SaveMemoryUpdate) => Promise<string | null>;
  flushPendingActions: (userId: string) => Promise<void>;
}

const BACKOFF_BASE_MS = 5_000;
const BACKOFF_MAX_MS = 5 * 60_000;

function _backoffDelayMs(attemptCount: number): number {
  return Math.min(BACKOFF_MAX_MS, BACKOFF_BASE_MS * 2 ** Math.max(0, attemptCount - 1));
}

function _isReadyToRetry(action: PendingSyncAction, now: number): boolean {
  if (action.attemptCount <= 0 || action.lastAttemptAt == null) return true;
  return now - action.lastAttemptAt >= _backoffDelayMs(action.attemptCount);
}

interface ErrorShape {
  response?: { status?: number };
  message?: string;
}

function _errorShape(err: unknown): ErrorShape {
  if (!err || typeof err !== 'object') return {};
  return err as ErrorShape;
}

function _classifyError(err: unknown, fallback: string): string {
  const shaped = _errorShape(err);
  const status = shaped.response?.status;
  if (status === 401) return 'auth_required';
  if (status === 429) return "You're doing that too fast — wait a moment and try again.";
  if (!shaped.response) return "Can't reach CRAVE — check your connection.";
  return fallback;
}

const _pendingSaves = new Set<string>();
let _flushInProgress = false;
let _loadSequence = 0;
let _accountGeneration = 0;
const _saveMutationToken = new Map<string, number>();

function _nextMutationToken(placeId: string): number {
  const next = (_saveMutationToken.get(placeId) ?? 0) + 1;
  _saveMutationToken.set(placeId, next);
  return next;
}

function _isCurrentMutation(placeId: string, token: number): boolean {
  return _saveMutationToken.get(placeId) === token;
}

function _makeEventId(): string {
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
}

function _enqueueSyncAction(
  set: (partial: Partial<CravesStore>) => void,
  get: () => CravesStore,
  placeId: string,
  type: 'add' | 'remove',
  userId: string,
  eventId: string,
  meta?: SaveEventMeta,
): void {
  const current = get().pendingSyncActions;
  const existing = current[placeId];

  // An offline add followed by an offline remove (or vice versa) before
  // either reaches the server cancels back to the server's known state.
  if (existing && existing.type !== type) {
    const next = { ...current };
    delete next[placeId];
    set({ pendingSyncActions: next });
    return;
  }

  set({
    pendingSyncActions: {
      ...current,
      [placeId]: {
        type,
        userId,
        queuedAt: existing?.queuedAt ?? Date.now(),
        attemptCount: (existing?.attemptCount ?? 0) + 1,
        lastAttemptAt: Date.now(),
        meta: existing?.meta ?? meta,
        eventId: existing?.eventId ?? eventId,
      },
    },
  });
}

function _logSaveOutcome(
  eventType: 'save' | 'unsave',
  placeId: string,
  eventId: string,
  ownerUserId: string,
  meta?: SaveEventMeta,
): void {
  // The owner is the userId captured by the mutation that produced this
  // confirmed server outcome — not whichever account happens to be active
  // by the time the Promise continuation runs. This closes the A->B switch
  // race for the durable recommendation outbox.
  logRecommendationEvent(
    {
      surface: meta?.surface ?? 'place_detail',
      event_type: eventType,
      place_id: placeId,
      position: meta?.position ?? null,
      rank_percentile: meta?.rank_percentile ?? null,
      city_id: meta?.city_id ?? null,
      query: meta?.query ?? null,
      client_event_id: eventId,
    },
    ownerUserId,
  );
}

function _resetForNewAccount(): void {
  _accountGeneration += 1;
  // Pending-add markers are keyed only by place id and therefore cannot
  // survive an account switch. Persisted sync actions are separately
  // account-owned and intentionally do survive.
  _pendingSaves.clear();
}

let _hydrationFailed = false;
const _hydrationWaiters: Array<() => void> = [];

function _resolveHydrationWaiters(): void {
  const waiters = _hydrationWaiters.splice(0, _hydrationWaiters.length);
  waiters.forEach((resolve) => resolve());
}

function _waitForHydration(): Promise<void> {
  if (useCravesStore.persist.hasHydrated() || _hydrationFailed) return Promise.resolve();
  return new Promise((resolve) => {
    const unsub = useCravesStore.persist.onFinishHydration(() => {
      unsub();
      resolve();
    });
    _hydrationWaiters.push(() => {
      unsub();
      resolve();
    });
  });
}

export const useCravesStore = create<CravesStore>()(
  persist(
    (set, get) => ({
      saves: [],
      loading: false,
      error: null,
      savesUserId: null,
      pendingSyncActions: {},

      loadSaves: async (userId: string) => {
        // Capture before hydration so sign-out can invalidate a call that is
        // still waiting for persisted state to finish loading.
        const mySequence = ++_loadSequence;
        await _waitForHydration();
        if (mySequence !== _loadSequence) return;

        // Only a cache explicitly owned by this account may remain visible
        // during reload. A different/unlabelled cache is cleared atomically
        // with its owner label before the network request starts.
        if (get().savesUserId !== userId) {
          _resetForNewAccount();
          set({ saves: [], savesUserId: userId });
        }

        set({ loading: true, error: null });
        try {
          const items = await fetchSaves(userId);
          if (mySequence !== _loadSequence) return;
          if (__DEV__) console.log('[CRAVES_STORE] loadSaves', { count: items.length });
          set({ saves: items, savesUserId: userId, loading: false });
          // Successful retrieval proves connectivity is available; drain this
          // account's durable offline mutation debt opportunistically.
          get().flushPendingActions(userId).catch(() => {});
        } catch (err: unknown) {
          if (mySequence !== _loadSequence) return;
          const msg = _classifyError(err, 'Failed to load saves');
          if (__DEV__) {
            console.log('[CRAVES_STORE] loadSaves_error', msg, _errorShape(err).response?.status);
          }
          set({ loading: false, error: msg });
        }
      },

      addSave: async (
        place: PlaceOut,
        userId: string,
        meta?: SaveEventMeta,
      ): Promise<string | null> => {
        const prev = get().saves;
        if (prev.find((saved) => saved.id === place.id) || _pendingSaves.has(place.id)) {
          return null;
        }

        const myGeneration = _accountGeneration;
        const myMutation = _nextMutationToken(place.id);
        const eventId = _makeEventId();
        _pendingSaves.add(place.id);

        const optimisticEntry: SavedPlace = {
          ...place,
          visited: false,
          visited_at: null,
          notes: null,
        };
        set({ saves: [optimisticEntry, ...prev] });

        try {
          await createSave(userId, place.id);
          if (__DEV__) console.log('[CRAVES_STORE] addSave_ok', place.id);
          _logSaveOutcome('save', place.id, eventId, userId, meta);
          return null;
        } catch (err: unknown) {
          const shaped = _errorShape(err);
          // Network-level failure is ambiguous: keep the user's optimistic
          // intent and queue an idempotent retry for this same account.
          if (!shaped.response) {
            if (myGeneration === _accountGeneration) {
              _enqueueSyncAction(set, get, place.id, 'add', userId, eventId, meta);
            }
            if (__DEV__) console.log('[CRAVES_STORE] addSave_queued_offline', place.id);
            return null;
          }

          if (myGeneration === _accountGeneration) {
            set({ saves: get().saves.filter((saved) => saved.id !== place.id) });
          }
          const msg = _classifyError(err, "Couldn't save. Try again.");
          if (__DEV__) {
            console.log('[CRAVES_STORE] addSave_error', shaped.response?.status, shaped.message);
          }
          return msg;
        } finally {
          if (_isCurrentMutation(place.id, myMutation)) {
            _pendingSaves.delete(place.id);
          }
        }
      },

      removeSave: async (
        placeId: string,
        userId: string,
        meta?: SaveEventMeta,
      ): Promise<string | null> => {
        const myGeneration = _accountGeneration;
        const myMutation = _nextMutationToken(placeId);
        const eventId = _makeEventId();
        const prev = get().saves;
        set({ saves: prev.filter((saved) => saved.id !== placeId) });

        try {
          await deleteSave(userId, placeId);
          if (__DEV__) console.log('[CRAVES_STORE] removeSave_ok', placeId);
          _logSaveOutcome('unsave', placeId, eventId, userId, meta);
          return null;
        } catch (err: unknown) {
          const shaped = _errorShape(err);
          if (!shaped.response) {
            if (myGeneration === _accountGeneration && _isCurrentMutation(placeId, myMutation)) {
              _enqueueSyncAction(set, get, placeId, 'remove', userId, eventId, meta);
              if (__DEV__) console.log('[CRAVES_STORE] removeSave_queued_offline', placeId);
            }
            return null;
          }

          if (myGeneration === _accountGeneration && _isCurrentMutation(placeId, myMutation)) {
            set({ saves: prev });
          }
          const msg = _classifyError(err, "Couldn't remove. Try again.");
          if (__DEV__) {
            console.log('[CRAVES_STORE] removeSave_error', shaped.response?.status, shaped.message);
          }
          return msg;
        }
      },

      clearSaves: () => {
        ++_loadSequence;
        _resetForNewAccount();
        if (__DEV__) console.log('[CRAVES_STORE] clearSaves');
        set({ saves: [], savesUserId: null, loading: false, error: null });
      },

      isSaved: (placeId: string) => get().saves.some((saved) => saved.id === placeId),

      setSaveMemory: async (
        placeId: string,
        updates: SaveMemoryUpdate,
      ): Promise<string | null> => {
        const prev = get().saves;
        const existing = prev.find((saved) => saved.id === placeId);
        if (!existing) return null;

        const myGeneration = _accountGeneration;
        const optimistic: SavedPlace = {
          ...existing,
          ...('visited' in updates
            ? {
                visited: !!updates.visited,
                visited_at: updates.visited ? new Date().toISOString() : null,
              }
            : {}),
          ...('notes' in updates ? { notes: updates.notes ?? null } : {}),
        };
        set({ saves: prev.map((saved) => (saved.id === placeId ? optimistic : saved)) });

        try {
          const result = await updateSaveMemory(placeId, updates);
          if (myGeneration !== _accountGeneration) return null;
          set({
            saves: get().saves.map((saved) =>
              saved.id === placeId ? { ...saved, ...result } : saved,
            ),
          });
          if (__DEV__) console.log('[CRAVES_STORE] setSaveMemory_ok', placeId, result);
          return null;
        } catch (err: unknown) {
          if (myGeneration === _accountGeneration) {
            set({
              saves: get().saves.map((saved) => (saved.id === placeId ? existing : saved)),
            });
          }
          const msg = _classifyError(err, "Couldn't save. Try again.");
          if (__DEV__) {
            const shaped = _errorShape(err);
            console.log('[CRAVES_STORE] setSaveMemory_error', shaped.response?.status, shaped.message);
          }
          return msg;
        }
      },

      flushPendingActions: async (userId: string) => {
        if (_flushInProgress) return;
        _flushInProgress = true;
        try {
          const entries = Object.entries(get().pendingSyncActions);
          const now = Date.now();

          for (const [placeId, action] of entries) {
            if (action.userId !== userId) continue;
            if (!_isReadyToRetry(action, now)) continue;

            try {
              if (action.type === 'add') {
                await createSave(userId, placeId);
              } else {
                try {
                  await deleteSave(userId, placeId);
                } catch (err: unknown) {
                  // 404 means the queued removal's desired state already
                  // exists server-side and is therefore a successful outcome.
                  if (_errorShape(err).response?.status !== 404) throw err;
                }
              }

              if (__DEV__) console.log('[CRAVES_STORE] flush_synced', placeId, action.type);
              _logSaveOutcome(
                action.type === 'add' ? 'save' : 'unsave',
                placeId,
                action.eventId ?? _makeEventId(),
                action.userId,
                action.meta,
              );

              set((state) => {
                const next = { ...state.pendingSyncActions };
                delete next[placeId];
                return { pendingSyncActions: next };
              });
            } catch (err: unknown) {
              const shaped = _errorShape(err);
              if (!shaped.response) {
                // Still offline. Record the attempt for exponential backoff
                // and stop this pass; later entries get another chance on a
                // subsequent foreground/successful-load trigger.
                set((state) => {
                  const stillQueued = state.pendingSyncActions[placeId];
                  if (!stillQueued) return state;
                  return {
                    pendingSyncActions: {
                      ...state.pendingSyncActions,
                      [placeId]: {
                        ...stillQueued,
                        attemptCount: stillQueued.attemptCount + 1,
                        lastAttemptAt: Date.now(),
                      },
                    },
                  };
                });
                return;
              }

              // A real non-network rejection will not become valid merely by
              // retrying forever (expired auth, forbidden request, etc.).
              if (__DEV__) console.log('[CRAVES_STORE] flush_drop', placeId, shaped.response?.status);
              set((state) => {
                const next = { ...state.pendingSyncActions };
                delete next[placeId];
                return { pendingSyncActions: next };
              });
            }
          }
        } finally {
          _flushInProgress = false;
        }
      },
    }),
    {
      name: 'crave-saves',
      storage: createJSONStorage(() => AsyncStorage),
      partialize: (state) => ({
        saves: state.saves,
        savesUserId: state.savesUserId,
        pendingSyncActions: state.pendingSyncActions,
      }),
      onRehydrateStorage: () => (_state, error) => {
        if (error) {
          if (__DEV__) console.log('[CRAVES_STORE] hydration_failed', error);
          _hydrationFailed = true;
          _resolveHydrationWaiters();
        }
      },
    },
  ),
);

// Drains the active account's offline queue on foreground. Entries for other
// accounts remain dormant until that account returns.
AppState.addEventListener('change', (state) => {
  if (state !== 'active') return;
  const userId = useCravesStore.getState().savesUserId;
  if (!userId) return;
  useCravesStore.getState().flushPendingActions(userId).catch(() => {});
});
