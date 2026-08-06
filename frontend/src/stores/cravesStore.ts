// Renamed from hitlistStore.ts — "Hitlist" was never the app's actual name
// for this feature (the tab bar label was "Saves", and the internal name
// drifted informally). The whole tab — bookmarked places + shared links —
// is called Craves. See app/(tabs)/craves.tsx.
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { PlaceOut } from '../api/places';
import { fetchSaves, createSave, deleteSave } from '../api/saves';

interface CravesStore {
  saves: PlaceOut[];
  loading: boolean;
  error: string | null;

  // Which account `saves` currently belongs to — persisted alongside
  // `saves` (see partialize below) specifically so it survives an app
  // restart. Without persisting this too, a restart's rehydrated `saves`
  // would have no way to prove which account they belong to, and — since
  // we can't safely assume unlabeled data belongs to whichever account
  // signs in next — the only safe default would be to distrust it and
  // clear on every restart, losing the whole point of caching saves
  // locally for instant display. Persisting the two together instead lets
  // a genuine same-account restart keep its cache while a different
  // account's leftover data still gets caught and cleared.
  savesUserId: string | null;

  // Load (or reload) saves from backend. Replaces local state.
  loadSaves: (userId: string) => Promise<void>;

  // Optimistic add — fires backend POST, rolls back on failure.
  // Returns error message string on failure, null on success.
  addSave: (place: PlaceOut, userId: string) => Promise<string | null>;

  // Optimistic remove — fires backend DELETE, rolls back on failure.
  // Returns error message string on failure, null on success.
  removeSave: (placeId: string, userId: string) => Promise<string | null>;

  // Clear all saves locally (call on sign-out).
  clearSaves: () => void;

  isSaved: (placeId: string) => boolean;
}

const _pendingSaves = new Set<string>();

// loadSaves() takes a userId but fetchSaves() has no request-cancellation
// mechanism — without this, a slow loadSaves() call for a just-signed-out
// account can resolve after a faster loadSaves() call for the newly
// signed-in account and overwrite the persisted `saves` state with the
// wrong account's data. Bumped at the start of each call (and by
// clearSaves(), so a request already in flight when sign-out happens can't
// repopulate the store afterward); a call only applies its result if it's
// still the most recently *started* one.
let _loadSequence = 0;

// Separate from _loadSequence, which bumps on *every* loadSaves() call
// (including a same-account pull-to-refresh — that must NOT invalidate a
// concurrent addSave/removeSave for the same account). This only bumps on
// an actual account change (clearSaves(), or loadSaves() detecting a
// savesUserId mismatch) — addSave/removeSave capture it at call time and
// check it before applying their post-await state updates, so a mutation
// still in flight when the account switches can't rollback-restore the
// *previous* account's full saves list, or optimistically-apply into the
// *new* account's list, after the fact.
let _accountGeneration = 0;

function _resetForNewAccount() {
  _accountGeneration += 1;
  // A pending add for one account must not silently block the same
  // place from being saved by a different account that signs in next —
  // _pendingSaves is keyed only by place.id, with no account scoping.
  _pendingSaves.clear();
}

// zustand persist rehydrates from AsyncStorage asynchronously — there's a
// real window right after the store is created where `saves`/`savesUserId`
// still read as their pre-hydration defaults ([]/null), not the actual
// persisted values from a previous session. If loadSaves() runs in that
// window it reads a `savesUserId` of `null` and, when rehydration finishes
// moments later, zustand's own rehydration set() applies the *persisted*
// (older) saves on top of whatever loadSaves() already wrote — silently
// reverting a fresher fetch result back to stale disk data. Waiting for
// hydration to finish before loadSaves() reads/writes anything closes that
// ordering gap.
function _waitForHydration(): Promise<void> {
  if (useCravesStore.persist.hasHydrated()) return Promise.resolve();
  return new Promise((resolve) => {
    const unsub = useCravesStore.persist.onFinishHydration(() => {
      unsub();
      resolve();
    });
  });
}

// Previously every failure (network error, 500, 429, expired session) was
// collapsed into one of two hardcoded strings, so a user hitting the rate
// limiter (see backend app/core/rate_limit.py) saw the exact same message
// as a genuine server crash, and an expired/invalid session ('auth_required')
// was set but never actually checked by any screen — so a signed-in user
// with a stale token just saw an infinite "retry" loop with no way out.
function _classifyError(err: any, fallback: string): string {
  const status = err?.response?.status;
  if (status === 401) return 'auth_required';
  if (status === 429) return "You're doing that too fast — wait a moment and try again.";
  if (!err?.response) return "Can't reach CRAVE — check your connection.";
  return fallback;
}

export const useCravesStore = create<CravesStore>()(
  persist(
    (set, get) => ({
      saves: [],
      loading: false,
      error: null,
      savesUserId: null,

      loadSaves: async (userId: string) => {
        await _waitForHydration();

        const mySequence = ++_loadSequence;
        // A different account than the one `saves` currently belongs to
        // (including a rehydrated-but-unlabeled-for-this-account cache,
        // which is exactly as untrustworthy as a known-different one) —
        // that data must not stay visible while this account's fetch is
        // in flight. `savesUserId === userId` (a genuine same-account
        // reload/restart) is the only case that skips this, preserving the
        // cached-saves-show-instantly UX for the one case where it's safe.
        //
        // saves and savesUserId are cleared/set together, atomically, not
        // left to land only once the fetch below succeeds — otherwise an
        // addSave/removeSave for the *new* account landing in this window
        // would optimistically write into `saves` while `savesUserId` still
        // named the *old* account, and if the app died right then, the
        // persisted pair on disk would be saves-from-B mislabeled as
        // belonging to A.
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
        } catch (err: any) {
          if (mySequence !== _loadSequence) return;
          const msg = _classifyError(err, 'Failed to load saves');
          if (__DEV__) console.log('[CRAVES_STORE] loadSaves_error', msg, err?.response?.status);
          set({ loading: false, error: msg });
        }
      },

      addSave: async (place: PlaceOut, userId: string): Promise<string | null> => {
        // Guard: skip if already saved or a concurrent add is in flight
        const prev = get().saves;
        if (prev.find((s) => s.id === place.id) || _pendingSaves.has(place.id)) {
          return null;
        }
        const myGeneration = _accountGeneration;
        _pendingSaves.add(place.id);
        // Optimistic: add immediately
        set({ saves: [place, ...prev] });
        try {
          await createSave(userId, place.id);
          if (__DEV__) console.log('[CRAVES_STORE] addSave_ok', place.id);
          return null;
        } catch (err: any) {
          // Rollback — but only into this same account's state. If the
          // account switched while this request was in flight, `saves`
          // now belongs to a different account entirely; touching it here
          // would inject (or filter) against the wrong account's list.
          if (myGeneration === _accountGeneration) {
            set({ saves: get().saves.filter((s) => s.id !== place.id) });
          }
          const msg = _classifyError(err, "Couldn't save. Try again.");
          if (__DEV__) console.log('[CRAVES_STORE] addSave_error', err?.response?.status, err?.message);
          return msg;
        } finally {
          _pendingSaves.delete(place.id);
        }
      },

      removeSave: async (placeId: string, userId: string): Promise<string | null> => {
        const myGeneration = _accountGeneration;
        // Optimistic: remove immediately
        const prev = get().saves;
        set({ saves: prev.filter((s) => s.id !== placeId) });
        try {
          await deleteSave(userId, placeId);
          if (__DEV__) console.log('[CRAVES_STORE] removeSave_ok', placeId);
          return null;
        } catch (err: any) {
          // Rollback — guarded the same way as addSave's: `prev` is this
          // account's full list captured at call time. If the account has
          // since switched (e.g. sign-out ran while this DELETE was still
          // in flight), restoring it now would splice the *previous*
          // account's entire saves list back into the store after
          // clearSaves() already ran.
          if (myGeneration === _accountGeneration) {
            set({ saves: prev });
          }
          const msg = _classifyError(err, "Couldn't remove. Try again.");
          if (__DEV__) console.log('[CRAVES_STORE] removeSave_error', err?.response?.status, err?.message);
          return msg;
        }
      },

      clearSaves: () => {
        // Invalidate any load already in flight — without this, a slow
        // fetchSaves() that started before sign-out could still resolve
        // afterward and repopulate the store with the just-signed-out
        // account's saves, since it would otherwise still match
        // _loadSequence.
        ++_loadSequence;
        // Also invalidate any in-flight addSave/removeSave (see their
        // guards above) and drop any pending-add markers so they can't
        // block the next account from saving the same place.
        _resetForNewAccount();
        if (__DEV__) console.log('[CRAVES_STORE] clearSaves');
        set({ saves: [], savesUserId: null, loading: false, error: null });
      },

      isSaved: (placeId: string) => get().saves.some((s) => s.id === placeId),
    }),
    {
      name: 'crave-saves',
      storage: createJSONStorage(() => AsyncStorage),
      // saves + savesUserId travel together — see savesUserId's comment.
      // loading/error are transient, not persisted.
      partialize: (state) => ({ saves: state.saves, savesUserId: state.savesUserId }),
    },
  ),
);
