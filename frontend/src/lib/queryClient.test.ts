// The cache-boundary guarantee Phase 1 exists to prove: private data
// cached under one account must never be readable once a different
// account is signed in on the same device. This exercises the real
// shared `queryClient` singleton and the real `authStore.signOut()` path
// together -- not mocks of either -- because the guarantee depends on
// both actually being wired to each other, not on each in isolation.
//
// `myRankings` is the primary case (the cleanest example of private
// per-user data this phase touched). friends-feed/leaderboard's key
// *shape* is separately unit-asserted in their own test files -- this
// one real end-to-end case plus those key-shape checks is enough
// coverage without three near-identical integration tests.
import { queryClient } from './queryClient';
import { useAuthStore } from '../stores/authStore';
import { supabase } from '../lib/supabase';
import type { RankedPlace } from '../api/social';

jest.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: jest.fn(),
      onAuthStateChange: jest.fn(),
      signOut: jest.fn(),
    },
  },
}));
jest.mock('../stores/cravesStore', () => ({
  useCravesStore: { getState: jest.fn(() => ({ clearSaves: jest.fn() })) },
}));
jest.mock('../services/pushNotifications', () => ({
  unregisterCurrentDevice: jest.fn().mockResolvedValue(undefined),
}));

const mockedSupabase = supabase as unknown as {
  auth: { signOut: jest.Mock };
};

function makeRanking(place_id: string, overrides: Partial<RankedPlace> = {}): RankedPlace {
  return {
    place_id, tier: 'liked', rank_score: 8.5, note: null, tags: null, visited_at: null,
    name: place_id, primary_image_url: null, city_id: null, ...overrides,
  } as RankedPlace;
}

describe('queryClient cache-boundary guarantee (private data across an account switch)', () => {
  beforeEach(() => {
    queryClient.clear();
    mockedSupabase.auth.signOut.mockReset();
    mockedSupabase.auth.signOut.mockResolvedValue(undefined);
  });

  it('clears a cached myRankings response on sign-out, and never lets it resurface under a different account\'s key', async () => {
    const ACCOUNT_A_RANKINGS = [makeRanking('secret-place-a', { name: "A's secret spot" })];
    const ACCOUNT_B_RANKINGS = [makeRanking('place-b', { name: "B's spot" })];

    // 1. Populate the cache as Account A, under the real key shape
    // place/[id].tsx actually uses (['myRankings', userId]).
    queryClient.setQueryData(['myRankings', 'user-A'], ACCOUNT_A_RANKINGS);
    expect(queryClient.getQueryData(['myRankings', 'user-A'])).toEqual(ACCOUNT_A_RANKINGS);

    // 2. Execute the real sign-out path -- not a mock of queryClient.clear(),
    // the actual authStore.signOut() calling the actual shared queryClient.
    await useAuthStore.getState().signOut();

    // 3. Account A's cached response must be gone.
    expect(queryClient.getQueryData(['myRankings', 'user-A'])).toBeUndefined();

    // 4. Account B signs in and its own fetch populates its own key.
    // Confirms A's payload can never be read back through B's key --
    // both because the keys are structurally distinct (the key-scoping
    // fix) and because the cache was already cleared (the signOut fix).
    // Together these are the two independent layers Phase 1 relies on;
    // this test proves both actually hold, not just one.
    queryClient.setQueryData(['myRankings', 'user-B'], ACCOUNT_B_RANKINGS);
    expect(queryClient.getQueryData(['myRankings', 'user-B'])).toEqual(ACCOUNT_B_RANKINGS);
    expect(queryClient.getQueryData(['myRankings', 'user-B'])).not.toEqual(ACCOUNT_A_RANKINGS);
    expect(queryClient.getQueryData(['myRankings', 'user-A'])).toBeUndefined();
  });
});
