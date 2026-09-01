// Renamed from hitlistStore.ts — "Hitlist" was never the app's actual name
// for this feature (the tab bar label was "Saves", and the internal name
// drifted informally). The whole tab — bookmarked places + shared links —
// is called Craves. See app/(tabs)/craves.tsx.
import { AppState } from 'react-native';
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { PlaceOut } from '../api/places';
import { fetchSaves, createSave, deleteSave, updateSaveMemory, SavedPlace, SaveMemoryUpdate } from '../api/saves';
import { logRecommendationEvent } from '../utils/recommendationEventQueue';
import { RecommendationSurface } from '../api/recommendationEvents';

// Optional context passed by the calling screen so a *confirmed* save/
// unsave outcome can be logged to the Recommendation Ledger with the
// same surface/position/percentile framing as that screen's own
// impression/click events. Deliberately not required: a caller with no
// natural surface (or that hasn't been wired up yet) just gets
// 'place_detail' as a reasonable default -- see addSave/removeSave.
export interface SaveEventMeta {
  surface?: RecommendationSurface;
  position?: number | null;
  rank_percentile?: number | null;
  city_id?: string | null;
  query?: string | null;
}

// A save/unsave that failed with a network-level error (no server response
// at all -- see _classifyError's `!err?.response` check) gets queued here
// instead of rolled back, so the user's action survives being offline and
// syncs once connectivity returns. Keyed by placeId rather than an array:
// an add queued while offline, followed by a remove for the same place
// before the queue ever flushes, should cancel out to "no network call
// needed" (the pre-existing server state already matches), not queue two
// contradictory ops -- see the enqueue logic in addSave/removeSave below.
export interface PendingSyncAction {
  type: 'add' | 'remove';
  userId: string;
  queuedAt: number;
  // How many sync attempts have failed with a network-level error so far
  // (0 = never attempted). Drives the exponential backoff below --
  // without it, every foreground/reconnect event retried every queued
  // entry immediately regardless of how recently it had just failed.
  attemptCount: number;
  // Timestamp of the most recent attempt, or null if never attempted.
  // Backoff is computed from THIS, not queuedAt -- using queuedAt would
  // make the delay shrink relative to "now" on every check instead of
  // resetting after each real attempt.
  lastAttemptAt: number | null;
  // Carried through from the addSave/removeSave call that first queued
  // this entry, so the Recommendation Ledger event logged once the sync
  // actually succeeds (see flushPendingActions) still has the surface/
  // position/percentile context of the screen the user acted from --
  // that context would otherwise be long gone by the time a later flush
  // pass (possibly a whole app restart later) confirms the outcome.
  meta?: SaveEventMeta;
  // Idempotency key for the eventual confirmed-outcome Ledger event --
  // generated once, at the moment this specific save/unsave attempt
  // first queues (see _makeEventId), and reused by every later retry of
  // *this same entry* rather than regenerated per attempt. Closes the
  // gap where a flush's removal of this entry is confirmed in memory and
  // its event logged, but the app is killed before that removal
  // persists to disk -- the next launch retries the (already-idempotent
  // server-side) sync call and would otherwise log a second event for
  // the same confirmed outcome; reusing the id lets the server drop the
  // resubmission as a duplicate instead. Optional only because an entry
  // already sitting in a signed-in user's persisted queue from before
  // this field existed won't have one -- flushPendingActions mints one
  // on the fly for that one-time case (see there).
  eventId?: string;
}

interface CravesStore {
  saves: SavedPlace[];
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

  // Offline-queued add/remove ops awaiting sync -- see PendingSyncAction.
  // Persisted (see partialize below) so a queued action survives an app
  // restart while still offline. Deliberately NOT scoped by savesUserId
  // the way `saves` is, and NOT cleared by clearSaves() on sign-out: each
  // entry already carries its own `userId`, flushPendingActions() only
  // ever acts on entries matching the userId it's called with, and a
  // queued action represents a real debt owed to that specific account's
  // server state -- it should still flush next time that account signs
  // back in and successfully loads, even if another account used the app
  // in between.
  pendingSyncActions: Record<string, PendingSyncAction>;

  // Load (or reload) saves from backend. Replaces local state.
  loadSaves: (userId: string) => Promise<void>;

  // Optimistic add — fires backend POST, rolls back on failure.
  // Returns error message string on failure, null on success. `meta`
  // (surface/position/percentile) is only used to log a Recommendation
  // Ledger 'save' event once the add is actually confirmed -- see the
  // module-level comment on SaveEventMeta.
  addSave: (place: PlaceOut, userId: string, meta?: SaveEventMeta) => Promise<string | null>;

  // Optimistic remove — fires backend DELETE, rolls back on failure.
  // Returns error message string on failure, null on success. Same
  // `meta` treatment as addSave, logging 'unsave' once confirmed.
  removeSave: (placeId: string, userId: string, meta?: SaveEventMeta) => Promise<string | null>;

  // Clear all saves locally (call on sign-out).
  clearSaves: () => void;

  isSaved: (placeId: string) => boolean;

  // Optimistic visited/notes update (E2) -- PATCHes
  // /saves/{placeId}/memory and applies the confirmed server response
  // (not just the local optimistic guess) into `saves` on success, so
  // e.g. visited_at reflects the server-stamped timestamp rather than a
  // client-side approximation. Rolls back to the pre-mutation entry on
  // failure. No-op (returns null) if the place isn't currently saved --
  // memory only exists on a save. Unlike addSave/removeSave, does not
  // queue on a network-level failure -- this is a lower-stakes edit than
  // a save/unsave, and the offline-queue machinery's account-generation
  // and mutation-token bookkeeping isn't worth duplicating for it.
  setSaveMemory: (placeId: string, updates: SaveMemoryUpdate) => Promise<string | null>;

  // Attempts every queued action belonging to `userId`, in order, stopping
  // at the first one that still fails with a network-level error (no point
  // trying the rest of the queue in the same pass if we're still offline --
  // it'll get another pass next time this is triggered). A non-network
  // failure (e.g. a 401 from a long-expired session) drops that single
  // entry rather than blocking the queue on it forever.
  flushPendingActions: (userId: string) => Promise<void>;
}

// Exponential backoff for flushPendingActions -- 5s, 10s, 20s... capped at
// 5 minutes. Ported from the reference offline-sync doc's backoffDelayMs
// formula, but computed from lastAttemptAt (the most recent real attempt)
// rather than that reference's createdAt/queuedAt, which was its actual
// bug: a delay measured from queue time only ever grows, so an entry
// queued long enough ago would look "due" on literally every check no
// matter how recently it had just failed again.
const BACKOFF_BASE_MS = 5_000;
const BACKOFF_MAX_MS = 5 * 60_000;

function _backoffDelayMs(attemptCount: number): number {
  return Math.min(BACKOFF_MAX_MS, BACKOFF_BASE_MS * 2 ** Math.max(0, attemptCount - 1));
}

function _isReadyToRetry(action: PendingSyncAction, now: number): boolean {
  if (action.attemptCount <= 0 || action.lastAttemptAt == null) return true;
  return now - action.lastAttemptAt >= _backoffDelayMs(action.attemptCount);
}

const _pendingSaves = new Set<string>();

// Guards flushPendingActions() against concurrent overlapping passes -- see
// its own comment for why this is just a wasted-work concern, not a
// correctness one.
let _flushInProgress = false;

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

// Per-place mutation token — addSave/removeSave for the same place.id can
// overlap (e.g. an account switch clears _pendingSaves mid-request, or a
// same-account double-tap), and _accountGeneration alone can't tell two
// overlapping operations for the *same* account apart. Without this, the
// older of two overlapping addSave calls could delete the newer one's
// _pendingSaves marker out from under it in its `finally`, or the older of
// two overlapping removeSave calls could restore its stale captured `prev`
// list after the newer removeSave already succeeded. Bumped once per
// addSave/removeSave call for a given placeId; a call only clears the
// pending marker or applies its rollback if its token is still current.
const _saveMutationToken = new Map<string, number>();

function _nextMutationToken(placeId: string): number {
  const next = (_saveMutationToken.get(placeId) ?? 0) + 1;
  _saveMutationToken.set(placeId, next);
  return next;
}

function _isCurrentMutation(placeId: string, token: number): boolean {
  return _saveMutationToken.get(placeId) === token;
}

// Queues (or cancels) an offline add/remove for `placeId`. A placeId with
// no existing queued entry gets one added. A placeId whose existing queued
// entry is the *opposite* type gets that entry deleted instead of
// replaced -- e.g. an add queued while offline, followed by a remove for
// the same place before the queue ever flushes, means the desired end
// state already matches what the server believes, so no network call is
// needed at all. A placeId whose existing entry is the *same* type just
// gets its queuedAt bumped (harmless overwrite -- same eventual API call).
// Generates a stable idempotency key for one save/unsave attempt's whole
// lifecycle (see PendingSyncAction.eventId's own comment) -- same shape
// as client.ts's existing requestId, no external uuid dependency needed.
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
) {
  const current = get().pendingSyncActions;
  const existing = current[placeId];
  if (existing && existing.type !== type) {
    const next = { ...current };
    delete next[placeId];
    set({ pendingSyncActions: next });
  } else {
    // Reaching this function at all means the direct addSave/removeSave
    // call that called it just failed with a network error -- that IS a
    // real attempt, so it counts toward backoff exactly like a
    // flushPendingActions retry failing would (see there for the other
    // half of this bookkeeping). eventId/meta are only ever taken from
    // `existing` when there is one -- this is still the same logical
    // attempt as whatever first queued this entry, so it must keep that
    // attempt's id, not mint a new one.
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
}

function _logSaveOutcome(
  eventType: 'save' | 'unsave',
  placeId: string,
  eventId: string,
  meta?: SaveEventMeta,
) {
  logRecommendationEvent({
    surface: meta?.surface ?? 'place_detail',
    event_type: eventType,
    place_id: placeId,
    position: meta?.position ?? null,
    rank_percentile: meta?.rank_percentile ?? null,
    city_id: meta?.city_id ?? null,
    query: meta?.query ?? null,
    client_event_id: eventId,
  });
}

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
//
// zustand's persist middleware only calls onFinishHydration's listeners on
// a *successful* rehydration — an AsyncStorage read failure runs the
// rejection path instead (only reaching onRehydrateStorage's error
// callback below), so hasHydrated() would stay false and any pending
// _waitForHydration() promise would never resolve at all. _hydrationFailed
// (set from that error callback) unblocks waiters in that case too, so a
// storage failure degrades to "proceed with in-memory defaults" instead of
// hanging loadSaves() forever.
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
      pendingSyncActions: {},

      loadSaves: async (userId: string) => {
        // Captured *before* awaiting hydration — a clearSaves() (sign-out)
        // that runs while this call is still waiting on
        // _waitForHydration() must be able to invalidate it. Capturing
        // this after the await instead would read the sequence clearSaves()
        // already bumped as this call's own starting point, so the
        // mismatch check below would never catch it — this call would
        // proceed to fetch and apply the just-signed-out account's saves
        // as if sign-out had never happened.
        const mySequence = ++_loadSequence;
        await _waitForHydration();
        if (mySequence !== _loadSequence) return;

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
          // A successful fetch proves connectivity is back -- opportunistic
          // trigger to drain anything queued while offline. Fire-and-forget:
          // flushPendingActions() never throws (each entry's own try/catch
          // handles its outcome), but .catch() is defensive insurance
          // against that invariant ever slipping.
          get().flushPendingActions(userId).catch(() => {});
        } catch (err: any) {
          if (mySequence !== _loadSequence) return;
          const msg = _classifyError(err, 'Failed to load saves');
          if (__DEV__) console.log('[CRAVES_STORE] loadSaves_error', msg, err?.response?.status);
          set({ loading: false, error: msg });
        }
      },

      addSave: async (place: PlaceOut, userId: string, meta?: SaveEventMeta): Promise<string | null> => {
        // Guard: skip if already saved or a concurrent add is in flight
        const prev = get().saves;
        if (prev.find((s) => s.id === place.id) || _pendingSaves.has(place.id)) {
          return null;
        }
        const myGeneration = _accountGeneration;
        // _resetForNewAccount() clears _pendingSaves on every account
        // switch, so a still-in-flight add from before the switch and a
        // fresh add for the same place.id started right after it can
        // genuinely overlap. Without this token, whichever of the two
        // finishes first would delete the *other's* still-pending marker
        // in its `finally` below, letting a third concurrent add through.
        const myMutation = _nextMutationToken(place.id);
        // Generated once per attempt and reused by any later flush retry
        // of this same entry (see PendingSyncAction.eventId) -- not
        // regenerated per network call, so a resubmission after the
        // process-kill-before-persist race dedupes server-side instead
        // of logging a second event for the same confirmed outcome.
        const eventId = _makeEventId();
        _pendingSaves.add(place.id);
        // Optimistic: add immediately. A freshly-saved place has no
        // memory yet -- the real values (if any existed from a prior
        // save/unsave/re-save cycle, which the backend's idempotent
        // "already_saved" path would actually preserve) arrive on the
        // next loadSaves(), same as any other server-side truth this
        // optimistic insert can't know yet.
        const optimisticEntry: SavedPlace = { ...place, visited: false, visited_at: null, notes: null };
        set({ saves: [optimisticEntry, ...prev] });
        try {
          await createSave(userId, place.id);
          if (__DEV__) console.log('[CRAVES_STORE] addSave_ok', place.id);
          _logSaveOutcome('save', place.id, eventId, meta);
          return null;
        } catch (err: any) {
          // A network-level failure (no server response at all -- the
          // request never reached the backend, as opposed to the backend
          // rejecting it) means we genuinely don't know whether this
          // succeeded server-side. Rather than rolling back a save the
          // user clearly asked for, keep the optimistic state and queue it
          // to retry once connectivity returns -- createSave() is
          // idempotent (see backend saves.py's "already_saved" path), so
          // a queued retry landing after a request that actually *did* get
          // through is harmless. No Ledger event yet: the outcome isn't
          // confirmed, only intended -- flushPendingActions logs it once
          // the retry actually succeeds.
          if (!err?.response) {
            if (myGeneration === _accountGeneration) {
              _enqueueSyncAction(set, get, place.id, 'add', userId, eventId, meta);
            }
            if (__DEV__) console.log('[CRAVES_STORE] addSave_queued_offline', place.id);
            return null;
          }
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
          // Only clear the marker if no newer add for this same place has
          // started since — otherwise this stale call's cleanup would drop
          // the marker a still-in-flight newer call still needs.
          if (_isCurrentMutation(place.id, myMutation)) {
            _pendingSaves.delete(place.id);
          }
        }
      },

      removeSave: async (placeId: string, userId: string, meta?: SaveEventMeta): Promise<string | null> => {
        const myGeneration = _accountGeneration;
        // Guards against two overlapping removeSave calls for the same
        // place (e.g. a rapid double-tap, or one from before an account
        // switch and one after) — without this, an older call's failure
        // rollback could restore its stale captured `prev` (which still
        // has the place in it) after a newer call already succeeded in
        // removing it, silently undoing the newer, correct removal.
        const myMutation = _nextMutationToken(placeId);
        // See addSave's identical comment on eventId.
        const eventId = _makeEventId();
        // Optimistic: remove immediately
        const prev = get().saves;
        set({ saves: prev.filter((s) => s.id !== placeId) });
        try {
          await deleteSave(userId, placeId);
          if (__DEV__) console.log('[CRAVES_STORE] removeSave_ok', placeId);
          _logSaveOutcome('unsave', placeId, eventId, meta);
          return null;
        } catch (err: any) {
          // Same offline-queue treatment as addSave: a network-level
          // failure means we don't know if the DELETE landed, so keep the
          // optimistic removal and queue a retry instead of restoring the
          // place. Guarded identically to the rollback below -- a stale,
          // superseded removeSave call (see the mutation-token comment on
          // this function) must not queue anything either. No Ledger
          // event here either, for the same "not confirmed yet" reason as
          // addSave's offline branch.
          if (!err?.response) {
            if (myGeneration === _accountGeneration && _isCurrentMutation(placeId, myMutation)) {
              _enqueueSyncAction(set, get, placeId, 'remove', userId, eventId, meta);
              if (__DEV__) console.log('[CRAVES_STORE] removeSave_queued_offline', placeId);
            }
            return null;
          }
          // Rollback — guarded the same way as addSave's: `prev` is this
          // account's full list captured at call time. If the account has
          // since switched (e.g. sign-out ran while this DELETE was still
          // in flight), restoring it now would splice the *previous*
          // account's entire saves list back into the store after
          // clearSaves() already ran. Also skipped if a newer removeSave
          // for this same place has since started (see myMutation above).
          if (myGeneration === _accountGeneration && _isCurrentMutation(placeId, myMutation)) {
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

      setSaveMemory: async (placeId: string, updates: SaveMemoryUpdate): Promise<string | null> => {
        const prev = get().saves;
        const existing = prev.find((s) => s.id === placeId);
        if (!existing) return null;

        const myGeneration = _accountGeneration;
        const optimistic: SavedPlace = {
          ...existing,
          ...('visited' in updates ? { visited: !!updates.visited, visited_at: updates.visited ? new Date().toISOString() : null } : {}),
          ...('notes' in updates ? { notes: updates.notes ?? null } : {}),
        };
        set({ saves: prev.map((s) => (s.id === placeId ? optimistic : s)) });

        try {
          const result = await updateSaveMemory(placeId, updates);
          if (myGeneration !== _accountGeneration) return null;
          // Reconcile with the server-confirmed values (e.g. the real
          // stamped visited_at) rather than trusting the optimistic guess.
          set({
            saves: get().saves.map((s) =>
              s.id === placeId ? { ...s, ...result } : s,
            ),
          });
          if (__DEV__) console.log('[CRAVES_STORE] setSaveMemory_ok', placeId, result);
          return null;
        } catch (err: any) {
          if (myGeneration === _accountGeneration) {
            set({ saves: get().saves.map((s) => (s.id === placeId ? existing : s)) });
          }
          const msg = _classifyError(err, "Couldn't save. Try again.");
          if (__DEV__) console.log('[CRAVES_STORE] setSaveMemory_error', err?.response?.status, err?.message);
          return msg;
        }
      },

      flushPendingActions: async (userId: string) => {
        // Cheap re-entrancy guard: loadSaves() and the AppState foreground
        // listener can both trigger a flush around the same moment (e.g.
        // app opens, Craves tab happens to already be mounted). Without
        // this, both passes would race to retry the same entries -- each
        // individual retry is harmless (idempotent add, 404-tolerant
        // remove), just wasteful.
        if (_flushInProgress) return;
        _flushInProgress = true;
        try {
          const entries = Object.entries(get().pendingSyncActions);
          const now = Date.now();
          for (const [placeId, action] of entries) {
            // Belongs to a different account than the one this flush call
            // is for -- leave it queued for when that account's own
            // loadSaves()/foreground flush comes around.
            if (action.userId !== userId) continue;

            // Still within its backoff window from the last failed
            // attempt -- skip it this pass (not the same as "stop the
            // whole pass" below: this is a per-entry timing gate, not a
            // connectivity signal, so later-queued entries that ARE due
            // still get their turn).
            if (!_isReadyToRetry(action, now)) continue;

            try {
              if (action.type === 'add') {
                await createSave(userId, placeId);
              } else {
                try {
                  await deleteSave(userId, placeId);
                } catch (err: any) {
                  // Already gone server-side -- exactly the state this
                  // queued remove was trying to reach, so treat it as
                  // success rather than an error to drop or retry.
                  if (err?.response?.status !== 404) throw err;
                }
              }
              if (__DEV__) console.log('[CRAVES_STORE] flush_synced', placeId, action.type);
              // action.eventId can be missing only for an entry persisted
              // before this field existed -- mint one on the spot, since
              // there's no earlier attempt for it to collide with anyway.
              _logSaveOutcome(action.type === 'add' ? 'save' : 'unsave', placeId, action.eventId ?? _makeEventId(), action.meta);
              set((state) => {
                const next = { ...state.pendingSyncActions };
                delete next[placeId];
                return { pendingSyncActions: next };
              });
            } catch (err: any) {
              if (!err?.response) {
                // Still offline -- record the attempt so this entry backs
                // off before the next pass retries it, then stop; the
                // rest of the queue gets another chance next time flush
                // is triggered. Guarded against the entry having been
                // cancelled out (opposite action queued) by something
                // else while this attempt's await was in flight.
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
              // A real (non-network) failure -- e.g. a session that's been
              // expired since before this device ever reconnected. Drop it
              // rather than blocking the queue on an entry that will never
              // succeed; the user's local state simply stays optimistic
              // until they take the action again.
              if (__DEV__) console.log('[CRAVES_STORE] flush_drop', placeId, err?.response?.status);
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
      // saves + savesUserId travel together — see savesUserId's comment.
      // pendingSyncActions must survive a restart too, or an app killed
      // while still offline would silently lose the queued action.
      // loading/error are transient, not persisted.
      partialize: (state) => ({
        saves: state.saves,
        savesUserId: state.savesUserId,
        pendingSyncActions: state.pendingSyncActions,
      }),
      // See _waitForHydration's comment — without this, an AsyncStorage
      // read failure would never call onFinishHydration's listeners at
      // all, and any loadSaves() call already waiting on hydration would
      // hang forever instead of proceeding with in-memory defaults.
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

// Drains any offline-queued save/unsave actions whenever the app returns to
// the foreground. loadSaves()'s own post-fetch flush only fires for
// whichever account actively reloads its saves (e.g. the Craves tab is
// visited) -- this covers the case where the user just reopens the app
// after being offline without necessarily going back to that tab.
AppState.addEventListener('change', (state) => {
  if (state !== 'active') return;
  const userId = useCravesStore.getState().savesUserId;
  if (!userId) return;
  useCravesStore.getState().flushPendingActions(userId).catch(() => {});
});
