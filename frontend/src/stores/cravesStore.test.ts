// Regression coverage for three CodeRabbit findings on the account-safety
// guards in cravesStore.ts:
//
// 1. loadSaves() used to capture its _loadSequence token *after* awaiting
//    hydration, so a clearSaves() (sign-out) that ran while the token still
//    matched the pre-hydration value could never be caught by the
//    mySequence check — the fetch would proceed and repopulate `saves` as
//    if sign-out had never happened.
// 2. addSave/removeSave only guarded against a stale *account* (via
//    _accountGeneration), not a stale *overlapping same-account/same-place*
//    mutation — an older removeSave's failure rollback could restore a
//    place a newer removeSave for the same place already removed.
// 3. _waitForHydration() only resolved via zustand persist's
//    onFinishHydration, which never fires if the AsyncStorage read itself
//    rejects — a storage failure left any pending loadSaves() call waiting
//    forever.
import type { SavedPlace } from '../api/saves';

let resolveGetItem: ((value: string | null) => void) | null = null;
let rejectGetItem: ((err: unknown) => void) | null = null;

jest.mock('@react-native-async-storage/async-storage', () => ({
  __esModule: true,
  default: {
    getItem: jest.fn(
      () =>
        new Promise((resolve, reject) => {
          resolveGetItem = resolve;
          rejectGetItem = reject;
        })
    ),
    setItem: jest.fn(() => Promise.resolve()),
    removeItem: jest.fn(() => Promise.resolve()),
  },
}));

jest.mock('../api/saves', () => ({
  fetchSaves: jest.fn(),
  createSave: jest.fn(),
  deleteSave: jest.fn(),
  updateSaveMemory: jest.fn(),
}));

// Real recommendationEventQueue.ts -> recommendationEvents.ts -> client.ts
// -> lib/supabase.ts, which throws at import time outside a real app
// process (no EXPO_PUBLIC_SUPABASE_URL env var here) -- same reason
// recommendationEventQueue.test.ts itself mocks one level down instead of
// letting that chain load for real.
jest.mock('../utils/recommendationEventQueue', () => ({
  logRecommendationEvent: jest.fn(),
}));

function makePlace(id: string): SavedPlace {
  return { id, name: id, visited: false, visited_at: null, notes: null } as unknown as SavedPlace;
}

// Several .then() hops separate our mock's resolve/reject call from the
// awaited code in loadSaves — give the microtask queue plenty of turns to
// drain rather than guessing the exact chain depth.
async function flush(): Promise<void> {
  for (let i = 0; i < 15; i++) {
    await Promise.resolve();
  }
}

describe('cravesStore', () => {
  let useCravesStore: typeof import('./cravesStore').useCravesStore;
  let savesApi: typeof import('../api/saves');
  let eventQueue: typeof import('../utils/recommendationEventQueue');

  beforeEach(() => {
    jest.resetModules();
    resolveGetItem = null;
    rejectGetItem = null;
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    savesApi = require('../api/saves');
    (savesApi.fetchSaves as jest.Mock).mockReset();
    (savesApi.createSave as jest.Mock).mockReset();
    (savesApi.deleteSave as jest.Mock).mockReset();
    (savesApi.updateSaveMemory as jest.Mock).mockReset();
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    eventQueue = require('../utils/recommendationEventQueue');
    (eventQueue.logRecommendationEvent as jest.Mock).mockReset();
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    ({ useCravesStore } = require('./cravesStore'));
  });

  async function hydrateWith(persistedState: string | null = null) {
    resolveGetItem?.(persistedState);
    await flush();
  }

  async function failHydrationWith(err: unknown) {
    rejectGetItem?.(err);
    await flush();
  }

  it('does not repopulate saves if clearSaves runs while loadSaves is still waiting on hydration', async () => {
    const loadPromise = useCravesStore.getState().loadSaves('userA');

    // Sign-out lands before AsyncStorage's read (and thus hydration) ever
    // resolves.
    useCravesStore.getState().clearSaves();

    (savesApi.fetchSaves as jest.Mock).mockResolvedValue([makePlace('p1')]);
    await hydrateWith(null);
    await loadPromise;

    expect(savesApi.fetchSaves).not.toHaveBeenCalled();
    expect(useCravesStore.getState().saves).toEqual([]);
    expect(useCravesStore.getState().savesUserId).toBeNull();
  });

  it('still loads saves normally when no sign-out races the hydration wait', async () => {
    const loadPromise = useCravesStore.getState().loadSaves('userA');
    (savesApi.fetchSaves as jest.Mock).mockResolvedValue([makePlace('p1')]);

    await hydrateWith(null);
    await loadPromise;

    expect(savesApi.fetchSaves).toHaveBeenCalledWith('userA');
    expect(useCravesStore.getState().saves).toEqual([makePlace('p1')]);
    expect(useCravesStore.getState().savesUserId).toBe('userA');
  });

  it('resolves a pending hydration wait instead of hanging when the AsyncStorage read fails', async () => {
    (savesApi.fetchSaves as jest.Mock).mockResolvedValue([makePlace('p1')]);
    const loadPromise = useCravesStore.getState().loadSaves('userA');

    await failHydrationWith(new Error('storage unavailable'));
    await loadPromise;

    expect(savesApi.fetchSaves).toHaveBeenCalledWith('userA');
    expect(useCravesStore.getState().saves).toEqual([makePlace('p1')]);
  });

  it('does not let an older failed removeSave restore a place a newer removeSave already removed', async () => {
    await hydrateWith(null);
    useCravesStore.setState({ saves: [makePlace('p1')], savesUserId: 'userA' });

    let rejectFirst: (err: unknown) => void = () => {};
    let resolveSecond: () => void = () => {};
    (savesApi.deleteSave as jest.Mock)
      .mockImplementationOnce(
        () =>
          new Promise((_resolve, reject) => {
            rejectFirst = reject;
          })
      )
      .mockImplementationOnce(
        () =>
          new Promise<void>((resolve) => {
            resolveSecond = resolve;
          })
      );

    const remove1 = useCravesStore.getState().removeSave('p1', 'userA');
    const remove2 = useCravesStore.getState().removeSave('p1', 'userA');

    resolveSecond();
    await remove2;
    expect(useCravesStore.getState().saves).toEqual([]);

    // remove1's rollback captured `prev` (=[p1]) before either removal ran.
    // Without the per-place mutation token, this stale failure would splice
    // p1 back in even though remove2 already correctly removed it.
    rejectFirst(new Error('network error'));
    await remove1;

    expect(useCravesStore.getState().saves).toEqual([]);
    // The stale remove1 must not queue a sync action either -- remove2
    // already fully completed the deletion server-side.
    expect(useCravesStore.getState().pendingSyncActions).toEqual({});
  });

  describe('offline outbox', () => {
    it('queues an add instead of rolling back when createSave fails with a network error', async () => {
      await hydrateWith(null);
      useCravesStore.setState({ saves: [], savesUserId: 'userA' });
      (savesApi.createSave as jest.Mock).mockRejectedValue(new Error('Network Error'));

      const result = await useCravesStore.getState().addSave(makePlace('p1'), 'userA');

      expect(result).toBeNull();
      expect(useCravesStore.getState().saves).toEqual([makePlace('p1')]);
      expect(useCravesStore.getState().pendingSyncActions).toEqual({
        p1: {
          type: 'add', userId: 'userA', queuedAt: expect.any(Number),
          attemptCount: 1, lastAttemptAt: expect.any(Number), eventId: expect.any(String),
        },
      });
    });

    it('queues a remove instead of restoring when deleteSave fails with a network error', async () => {
      await hydrateWith(null);
      useCravesStore.setState({ saves: [makePlace('p1')], savesUserId: 'userA' });
      (savesApi.deleteSave as jest.Mock).mockRejectedValue(new Error('Network Error'));

      const result = await useCravesStore.getState().removeSave('p1', 'userA');

      expect(result).toBeNull();
      expect(useCravesStore.getState().saves).toEqual([]);
      expect(useCravesStore.getState().pendingSyncActions).toEqual({
        p1: {
          type: 'remove', userId: 'userA', queuedAt: expect.any(Number),
          attemptCount: 1, lastAttemptAt: expect.any(Number), eventId: expect.any(String),
        },
      });
    });

    it('cancels a queued add when the same place is removed again before the queue flushes', async () => {
      await hydrateWith(null);
      useCravesStore.setState({ saves: [], savesUserId: 'userA' });
      (savesApi.createSave as jest.Mock).mockRejectedValue(new Error('Network Error'));
      (savesApi.deleteSave as jest.Mock).mockRejectedValue(new Error('Network Error'));

      await useCravesStore.getState().addSave(makePlace('p1'), 'userA');
      expect(useCravesStore.getState().pendingSyncActions).toHaveProperty('p1');

      await useCravesStore.getState().removeSave('p1', 'userA');

      // Desired end state (not saved) already matches what the server
      // believes -- no network call should ever be needed for this place.
      expect(useCravesStore.getState().pendingSyncActions).toEqual({});
    });

    it('cancels a queued remove when the same place is saved again before the queue flushes', async () => {
      await hydrateWith(null);
      useCravesStore.setState({ saves: [makePlace('p1')], savesUserId: 'userA' });
      (savesApi.deleteSave as jest.Mock).mockRejectedValue(new Error('Network Error'));
      (savesApi.createSave as jest.Mock).mockRejectedValue(new Error('Network Error'));

      await useCravesStore.getState().removeSave('p1', 'userA');
      expect(useCravesStore.getState().pendingSyncActions).toHaveProperty('p1');

      await useCravesStore.getState().addSave(makePlace('p1'), 'userA');

      expect(useCravesStore.getState().pendingSyncActions).toEqual({});
    });

    it('flushPendingActions syncs a queued add and clears it from the queue', async () => {
      await hydrateWith(null);
      useCravesStore.setState({
        pendingSyncActions: {
          p1: { type: 'add', userId: 'userA', queuedAt: 1, attemptCount: 0, lastAttemptAt: null },
        },
      });
      (savesApi.createSave as jest.Mock).mockResolvedValue(undefined);

      await useCravesStore.getState().flushPendingActions('userA');

      expect(savesApi.createSave).toHaveBeenCalledWith('userA', 'p1');
      expect(useCravesStore.getState().pendingSyncActions).toEqual({});
    });

    it('flushPendingActions treats a 404 on a queued remove as already-synced, not a failure', async () => {
      await hydrateWith(null);
      useCravesStore.setState({
        pendingSyncActions: {
          p1: { type: 'remove', userId: 'userA', queuedAt: 1, attemptCount: 0, lastAttemptAt: null },
        },
      });
      (savesApi.deleteSave as jest.Mock).mockRejectedValue({ response: { status: 404 } });

      await useCravesStore.getState().flushPendingActions('userA');

      expect(useCravesStore.getState().pendingSyncActions).toEqual({});
    });

    it('flushPendingActions stops at the first still-offline entry and leaves the rest queued', async () => {
      await hydrateWith(null);
      useCravesStore.setState({
        pendingSyncActions: {
          p1: { type: 'add', userId: 'userA', queuedAt: 1, attemptCount: 0, lastAttemptAt: null },
          p2: { type: 'add', userId: 'userA', queuedAt: 2, attemptCount: 0, lastAttemptAt: null },
        },
      });
      (savesApi.createSave as jest.Mock).mockRejectedValue(new Error('Network Error'));

      await useCravesStore.getState().flushPendingActions('userA');

      expect(savesApi.createSave).toHaveBeenCalledTimes(1);
      expect(useCravesStore.getState().pendingSyncActions).toEqual({
        // The failed attempt is recorded (attemptCount bumped, lastAttemptAt
        // stamped) so it backs off before the next pass retries it.
        p1: { type: 'add', userId: 'userA', queuedAt: 1, attemptCount: 1, lastAttemptAt: expect.any(Number) },
        // Never reached this pass -- the loop returned after p1's failure.
        p2: { type: 'add', userId: 'userA', queuedAt: 2, attemptCount: 0, lastAttemptAt: null },
      });
    });

    it('flushPendingActions drops an entry that fails with a real (non-network) error', async () => {
      await hydrateWith(null);
      useCravesStore.setState({
        pendingSyncActions: {
          p1: { type: 'add', userId: 'userA', queuedAt: 1, attemptCount: 0, lastAttemptAt: null },
        },
      });
      (savesApi.createSave as jest.Mock).mockRejectedValue({ response: { status: 401 } });

      await useCravesStore.getState().flushPendingActions('userA');

      expect(useCravesStore.getState().pendingSyncActions).toEqual({});
    });

    it('flushPendingActions leaves entries belonging to a different account untouched', async () => {
      await hydrateWith(null);
      useCravesStore.setState({
        pendingSyncActions: {
          p1: { type: 'add', userId: 'userB', queuedAt: 1, attemptCount: 0, lastAttemptAt: null },
        },
      });

      await useCravesStore.getState().flushPendingActions('userA');

      expect(savesApi.createSave).not.toHaveBeenCalled();
      expect(useCravesStore.getState().pendingSyncActions).toEqual({
        p1: { type: 'add', userId: 'userB', queuedAt: 1, attemptCount: 0, lastAttemptAt: null },
      });
    });

    describe('exponential backoff', () => {
      it('skips a queued entry still within its backoff window', async () => {
        await hydrateWith(null);
        const now = Date.now();
        useCravesStore.setState({
          pendingSyncActions: {
            // attemptCount 1 -> 5s backoff; only 1s has actually elapsed.
            p1: { type: 'add', userId: 'userA', queuedAt: 1, attemptCount: 1, lastAttemptAt: now - 1_000 },
          },
        });

        await useCravesStore.getState().flushPendingActions('userA');

        expect(savesApi.createSave).not.toHaveBeenCalled();
        // Left untouched -- not even attemptCount bumped, since it was
        // never actually attempted this pass.
        expect(useCravesStore.getState().pendingSyncActions.p1.attemptCount).toBe(1);
      });

      it('retries a queued entry once its backoff window has elapsed', async () => {
        await hydrateWith(null);
        const now = Date.now();
        useCravesStore.setState({
          pendingSyncActions: {
            // attemptCount 1 -> 5s backoff; 10s have elapsed, so it's due.
            p1: { type: 'add', userId: 'userA', queuedAt: 1, attemptCount: 1, lastAttemptAt: now - 10_000 },
          },
        });
        (savesApi.createSave as jest.Mock).mockResolvedValue(undefined);

        await useCravesStore.getState().flushPendingActions('userA');

        expect(savesApi.createSave).toHaveBeenCalledWith('userA', 'p1');
        expect(useCravesStore.getState().pendingSyncActions).toEqual({});
      });

      it('does not let a due entry block a later, still-backing-off entry from being skipped correctly', async () => {
        await hydrateWith(null);
        const now = Date.now();
        useCravesStore.setState({
          pendingSyncActions: {
            p1: { type: 'add', userId: 'userA', queuedAt: 1, attemptCount: 1, lastAttemptAt: now - 10_000 }, // due
            p2: { type: 'add', userId: 'userA', queuedAt: 2, attemptCount: 1, lastAttemptAt: now - 1_000 },  // not due
          },
        });
        (savesApi.createSave as jest.Mock).mockResolvedValue(undefined);

        await useCravesStore.getState().flushPendingActions('userA');

        expect(savesApi.createSave).toHaveBeenCalledTimes(1);
        expect(savesApi.createSave).toHaveBeenCalledWith('userA', 'p1');
        expect(useCravesStore.getState().pendingSyncActions).toEqual({
          p2: { type: 'add', userId: 'userA', queuedAt: 2, attemptCount: 1, lastAttemptAt: now - 1_000 },
        });
      });

      it('grows the delay with each additional failed attempt', async () => {
        await hydrateWith(null);
        const now = Date.now();
        useCravesStore.setState({
          pendingSyncActions: {
            // attemptCount 3 -> 20s backoff; only 10s elapsed, still due to wait.
            p1: { type: 'add', userId: 'userA', queuedAt: 1, attemptCount: 3, lastAttemptAt: now - 10_000 },
          },
        });

        await useCravesStore.getState().flushPendingActions('userA');

        expect(savesApi.createSave).not.toHaveBeenCalled();
      });
    });
  });

  describe('Recommendation Ledger outcome logging', () => {
    // The whole point: log a *confirmed* domain outcome, never a tap. A
    // save/remove that only got as far as "queued, network status
    // unknown" must not log anything -- see the other assertions below.
    it('logs a save event immediately when createSave confirms synchronously', async () => {
      await hydrateWith(null);
      useCravesStore.setState({ saves: [], savesUserId: 'userA' });
      (savesApi.createSave as jest.Mock).mockResolvedValue(undefined);

      await useCravesStore.getState().addSave(makePlace('p1'), 'userA', {
        surface: 'feed', rank_percentile: 0.9, city_id: 'city-1',
      });

      expect(eventQueue.logRecommendationEvent).toHaveBeenCalledTimes(1);
      expect(eventQueue.logRecommendationEvent).toHaveBeenCalledWith({
        surface: 'feed', event_type: 'save', place_id: 'p1',
        position: null, rank_percentile: 0.9, city_id: 'city-1', query: null,
        client_event_id: expect.any(String),
      });
    });

    it('logs an unsave event immediately when deleteSave confirms synchronously', async () => {
      await hydrateWith(null);
      useCravesStore.setState({ saves: [makePlace('p1')], savesUserId: 'userA' });
      (savesApi.deleteSave as jest.Mock).mockResolvedValue(undefined);

      await useCravesStore.getState().removeSave('p1', 'userA', { surface: 'craves' });

      expect(eventQueue.logRecommendationEvent).toHaveBeenCalledTimes(1);
      expect(eventQueue.logRecommendationEvent).toHaveBeenCalledWith(
        expect.objectContaining({ surface: 'craves', event_type: 'unsave', place_id: 'p1' }),
      );
    });

    it('defaults to place_detail surface when no meta is passed', async () => {
      await hydrateWith(null);
      useCravesStore.setState({ saves: [], savesUserId: 'userA' });
      (savesApi.createSave as jest.Mock).mockResolvedValue(undefined);

      await useCravesStore.getState().addSave(makePlace('p1'), 'userA');

      expect(eventQueue.logRecommendationEvent).toHaveBeenCalledWith(
        expect.objectContaining({ surface: 'place_detail', event_type: 'save' }),
      );
    });

    it('does not log anything when a save is only queued offline, not yet confirmed', async () => {
      await hydrateWith(null);
      useCravesStore.setState({ saves: [], savesUserId: 'userA' });
      (savesApi.createSave as jest.Mock).mockRejectedValue(new Error('Network Error'));

      await useCravesStore.getState().addSave(makePlace('p1'), 'userA', { surface: 'feed' });

      expect(eventQueue.logRecommendationEvent).not.toHaveBeenCalled();
      expect(useCravesStore.getState().pendingSyncActions.p1.meta).toEqual({ surface: 'feed' });
    });

    it('does not log anything when a real (non-network) failure rolls back the save', async () => {
      await hydrateWith(null);
      useCravesStore.setState({ saves: [], savesUserId: 'userA' });
      (savesApi.createSave as jest.Mock).mockRejectedValue({ response: { status: 500 } });

      await useCravesStore.getState().addSave(makePlace('p1'), 'userA', { surface: 'feed' });

      expect(eventQueue.logRecommendationEvent).not.toHaveBeenCalled();
    });

    it('logs the save event once a queued add is confirmed by a later flush, using the meta captured at queue time', async () => {
      await hydrateWith(null);
      useCravesStore.setState({
        pendingSyncActions: {
          p1: {
            type: 'add', userId: 'userA', queuedAt: 1, attemptCount: 0, lastAttemptAt: null,
            meta: { surface: 'search', rank_percentile: 0.5 },
          },
        },
      });
      (savesApi.createSave as jest.Mock).mockResolvedValue(undefined);

      await useCravesStore.getState().flushPendingActions('userA');

      expect(eventQueue.logRecommendationEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          surface: 'search', event_type: 'save', place_id: 'p1', rank_percentile: 0.5,
          client_event_id: expect.any(String),
        }),
      );
    });

    it('does not log anything for an entry flushPendingActions leaves queued (still offline)', async () => {
      await hydrateWith(null);
      useCravesStore.setState({
        pendingSyncActions: {
          p1: { type: 'add', userId: 'userA', queuedAt: 1, attemptCount: 0, lastAttemptAt: null },
        },
      });
      (savesApi.createSave as jest.Mock).mockRejectedValue(new Error('Network Error'));

      await useCravesStore.getState().flushPendingActions('userA');

      expect(eventQueue.logRecommendationEvent).not.toHaveBeenCalled();
    });

    // The actual invariant this whole idempotency-key mechanism exists
    // for: "one confirmed state transition -> at most one ledger outcome
    // event", even across a failed-then-successful retry sequence, so a
    // resubmission after the offline-outbox's own process-kill-before-
    // persist race (see PendingSyncAction.eventId's docstring) is safe to
    // dedupe server-side instead of double-counting.
    it('reuses the same client_event_id across a failed retry and the eventual successful sync', async () => {
      await hydrateWith(null);
      useCravesStore.setState({ saves: [], savesUserId: 'userA' });
      (savesApi.createSave as jest.Mock).mockRejectedValue(new Error('Network Error'));

      await useCravesStore.getState().addSave(makePlace('p1'), 'userA', { surface: 'feed' });
      const queuedEventId = useCravesStore.getState().pendingSyncActions.p1.eventId;
      expect(queuedEventId).toEqual(expect.any(String));
      expect(eventQueue.logRecommendationEvent).not.toHaveBeenCalled();

      // First flush attempt still fails -- the entry stays queued and
      // must keep the exact same id, not mint a new one per attempt.
      await useCravesStore.getState().flushPendingActions('userA');
      expect(useCravesStore.getState().pendingSyncActions.p1.eventId).toBe(queuedEventId);
      expect(eventQueue.logRecommendationEvent).not.toHaveBeenCalled();

      // Second flush attempt succeeds -- exactly one log, carrying the
      // same id that was generated back when this action first queued.
      // Backs the backoff window up so this attempt is actually due
      // (not exercising backoff timing itself, covered elsewhere).
      useCravesStore.setState((state) => ({
        pendingSyncActions: {
          ...state.pendingSyncActions,
          p1: { ...state.pendingSyncActions.p1, lastAttemptAt: Date.now() - 60_000 },
        },
      }));
      (savesApi.createSave as jest.Mock).mockResolvedValue(undefined);
      await useCravesStore.getState().flushPendingActions('userA');

      expect(eventQueue.logRecommendationEvent).toHaveBeenCalledTimes(1);
      expect(eventQueue.logRecommendationEvent).toHaveBeenCalledWith(
        expect.objectContaining({ event_type: 'save', place_id: 'p1', client_event_id: queuedEventId }),
      );
      expect(useCravesStore.getState().pendingSyncActions).toEqual({});
    });
  });

  describe('setSaveMemory', () => {
    it('applies the server-confirmed visited_at rather than the optimistic guess', async () => {
      await hydrateWith(null);
      useCravesStore.setState({ saves: [makePlace('p1')], savesUserId: 'userA' });
      (savesApi.updateSaveMemory as jest.Mock).mockResolvedValue({
        visited: true, visited_at: '2026-09-01T12:00:00Z', notes: null,
      });

      const err = await useCravesStore.getState().setSaveMemory('p1', { visited: true });

      expect(err).toBeNull();
      const saved = useCravesStore.getState().saves.find((s) => s.id === 'p1');
      expect(saved?.visited).toBe(true);
      expect(saved?.visited_at).toBe('2026-09-01T12:00:00Z');
    });

    it('rolls back to the pre-mutation entry on failure', async () => {
      await hydrateWith(null);
      const original = makePlace('p1');
      useCravesStore.setState({ saves: [original], savesUserId: 'userA' });
      (savesApi.updateSaveMemory as jest.Mock).mockRejectedValue({
        response: { status: 500 },
      });

      const err = await useCravesStore.getState().setSaveMemory('p1', { visited: true });

      expect(err).not.toBeNull();
      expect(useCravesStore.getState().saves.find((s) => s.id === 'p1')).toEqual(original);
    });

    it('is a no-op when the place is not currently saved', async () => {
      await hydrateWith(null);
      useCravesStore.setState({ saves: [], savesUserId: 'userA' });

      const err = await useCravesStore.getState().setSaveMemory('p1', { visited: true });

      expect(err).toBeNull();
      expect(savesApi.updateSaveMemory).not.toHaveBeenCalled();
    });

    it('clears notes when explicitly set to null, leaves visited untouched', async () => {
      await hydrateWith(null);
      useCravesStore.setState({
        saves: [{ ...makePlace('p1'), notes: 'old note', visited: true }],
        savesUserId: 'userA',
      });
      (savesApi.updateSaveMemory as jest.Mock).mockResolvedValue({
        visited: true, visited_at: null, notes: null,
      });

      await useCravesStore.getState().setSaveMemory('p1', { notes: null });

      expect(savesApi.updateSaveMemory).toHaveBeenCalledWith('p1', { notes: null });
      const saved = useCravesStore.getState().saves.find((s) => s.id === 'p1');
      expect(saved?.notes).toBeNull();
      expect(saved?.visited).toBe(true);
    });
  });
});
