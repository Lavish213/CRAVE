// Profile screen (app/(tabs)/profile.tsx) — first dedicated coverage.
// Locks in: the signed-out / no-username / loaded-with-data state
// machine, conditional UI (streak tile, "unlock" nudge below the
// recommendation threshold, Taste Profile link only once something's
// ranked), navigation from a ranked row, and the account-switch stale-
// response guard (same shape as cravesStore's, load()'s own
// loadGenerationRef).
import React from 'react';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';
import ProfileScreen from '../app/(tabs)/profile';
import { useAuthStore } from '../src/stores/authStore';
import {
  Profile, RankedPlace, fetchFollowers, fetchFollowing, fetchMyProfile, fetchMyRankings,
} from '../src/api/social';
import { fetchMyStreak } from '../src/api/streak';

const mockPush = jest.fn();
jest.mock('expo-router', () => ({
  useRouter: () => ({ push: mockPush }),
  // Fires on every mount, matching the real navigator's initial-focus
  // behavior closely enough for this screen's "re-read on focus" intent
  // -- there is no actual tab-switch to simulate under RTL.
  useFocusEffect: (cb: () => void) => require('react').useEffect(cb, [cb]),
}));
jest.mock('../src/stores/authStore', () => ({
  useAuthStore: jest.fn(),
}));
jest.mock('../src/api/social', () => ({
  fetchMyProfile: jest.fn(),
  fetchMyRankings: jest.fn(),
  fetchFollowing: jest.fn(),
  fetchFollowers: jest.fn(),
}));
jest.mock('../src/api/streak', () => ({
  fetchMyStreak: jest.fn(),
}));
jest.mock('../src/components/AuthSheet', () => {
  const { Text } = require('react-native');
  return {
    AuthSheet: ({ visible }: { visible: boolean }) =>
      visible ? <Text testID="auth-sheet-visible">auth</Text> : null,
  };
});

const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;
const mockedFetchMyProfile = fetchMyProfile as jest.MockedFunction<typeof fetchMyProfile>;
const mockedFetchMyRankings = fetchMyRankings as jest.MockedFunction<typeof fetchMyRankings>;
const mockedFetchFollowing = fetchFollowing as jest.MockedFunction<typeof fetchFollowing>;
const mockedFetchFollowers = fetchFollowers as jest.MockedFunction<typeof fetchFollowers>;
const mockedFetchMyStreak = fetchMyStreak as jest.MockedFunction<typeof fetchMyStreak>;

function makeProfile(overrides: Partial<Profile> = {}): Profile {
  return { id: 'user-1', username: 'alice', display_name: 'Alice', avatar_url: null, bio: null, is_public: true, ...overrides };
}
function makeRanking(place_id: string, overrides: Partial<RankedPlace> = {}): RankedPlace {
  return {
    place_id, tier: 'liked', rank_score: 8.5, note: null, tags: null, visited_at: null,
    name: place_id, primary_image_url: null, city_id: 'city-sf', ...overrides,
  } as RankedPlace;
}

function setAuthedUser(user: { id: string } | null) {
  mockedUseAuthStore.mockImplementation((selector: (s: { user: unknown }) => unknown) => selector({ user }));
}

describe('ProfileScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedFetchMyProfile.mockResolvedValue(makeProfile());
    mockedFetchMyRankings.mockResolvedValue([]);
    mockedFetchFollowing.mockResolvedValue([]);
    mockedFetchFollowers.mockResolvedValue([]);
    mockedFetchMyStreak.mockResolvedValue({ current_streak: 0, longest_streak: 0, last_active_date: null });
  });

  it('shows a sign-in prompt when signed out, and opens AuthSheet from its CTA', async () => {
    setAuthedUser(null);
    const { getByText, findByTestId } = render(<ProfileScreen />);

    expect(getByText('Sign in to build your list')).toBeTruthy();
    fireEvent.press(getByText('Sign in'));
    expect(await findByTestId('auth-sheet-visible')).toBeTruthy();
  });

  it('prompts to choose a username when signed in but no profile exists yet', async () => {
    setAuthedUser({ id: 'user-1' });
    mockedFetchMyProfile.mockResolvedValue(null);

    const { findByText } = render(<ProfileScreen />);
    const cta = await findByText('Choose username');
    fireEvent.press(cta);
    expect(mockPush).toHaveBeenCalledWith('/profile-setup');
  });

  it('does not mistake a failed profile request for a missing username', async () => {
    setAuthedUser({ id: 'user-1' });
    mockedFetchMyProfile.mockRejectedValue(new Error('network'));

    const { findByText, queryByText } = render(<ProfileScreen />);

    expect(await findByText("Couldn't load your profile")).toBeTruthy();
    expect(queryByText('Pick a username')).toBeNull();
  });

  it('renders profile header, stats, and the below-threshold unlock nudge (no streak tile at zero)', async () => {
    setAuthedUser({ id: 'user-1' });
    mockedFetchMyRankings.mockResolvedValue([makeRanking('p0'), makeRanking('p1')]);
    mockedFetchFollowing.mockResolvedValue(['f1']);
    mockedFetchFollowers.mockResolvedValue(['f1', 'f2']);

    const { findByText, queryByLabelText } = render(<ProfileScreen />);

    expect(await findByText('Alice')).toBeTruthy();
    expect(await findByText('@alice')).toBeTruthy();
    expect(await findByText(/2 places ranked/)).toBeTruthy();
    expect(queryByLabelText(/day streak/)).toBeNull();
    // Below RECOMMENDATION_THRESHOLD (15) with only 2 ranked -- the nudge
    // must be visible.
    expect(await findByText(/Rank 13 more places/)).toBeTruthy();
  });

  it('shows the streak tile once current_streak is positive, and hides the unlock nudge once at threshold', async () => {
    setAuthedUser({ id: 'user-1' });
    mockedFetchMyRankings.mockResolvedValue(
      Array.from({ length: 15 }, (_, i) => makeRanking(`p${i}`)),
    );
    // A streak value that can't collide with any RankedPlaceRow's own
    // visible position number (1-15 are all rendered as plain text too).
    mockedFetchMyStreak.mockResolvedValue({ current_streak: 99, longest_streak: 9, last_active_date: '2026-08-25' });

    // The streak StatTile has no onPress, so (per StatTile's own
    // implementation) it never gets wrapped in the pressable branch that
    // sets an accessibilityLabel -- assert on its rendered text instead.
    const { findByText, queryByText } = render(<ProfileScreen />);

    expect(await findByText('99')).toBeTruthy();
    expect(await findByText('day streak')).toBeTruthy();
    expect(queryByText(/Rank .* more/)).toBeNull();
  });

  it('hides the Taste Profile link and shows the empty-list state with its CTA when nothing is ranked', async () => {
    setAuthedUser({ id: 'user-1' });
    const { findByText, queryByLabelText } = render(<ProfileScreen />);
    await findByText('Nothing ranked yet');
    expect(queryByLabelText('Your Taste Profile')).toBeNull();

    fireEvent.press(await findByText('Browse places'));
    expect(mockPush).toHaveBeenCalledWith('/');
  });

  it('does not mistake a failed rankings request for an empty list', async () => {
    setAuthedUser({ id: 'user-1' });
    mockedFetchMyRankings.mockRejectedValue(new Error('network'));

    const { findByText, queryByText } = render(<ProfileScreen />);

    expect(await findByText("Couldn't load your ranked places")).toBeTruthy();
    expect(queryByText('Nothing ranked yet')).toBeNull();
  });

  it('shows unavailable stats instead of false zeroes when social reads fail', async () => {
    setAuthedUser({ id: 'user-1' });
    mockedFetchFollowing.mockRejectedValue(new Error('network'));
    mockedFetchFollowers.mockRejectedValue(new Error('network'));
    mockedFetchMyStreak.mockRejectedValue(new Error('network'));

    const { findAllByText, findByText } = render(<ProfileScreen />);

    expect((await findAllByText('—')).length).toBe(3);
    expect(await findByText('day streak')).toBeTruthy();
  });

  it('shows the Taste Profile link and navigates to a ranked row', async () => {
    setAuthedUser({ id: 'user-1' });
    mockedFetchMyRankings.mockResolvedValue([makeRanking('p0', { name: 'Tasty Spot', rank_score: 9.1 })]);

    const { findByLabelText } = render(<ProfileScreen />);
    expect(await findByLabelText('Your Taste Profile')).toBeTruthy();

    const row = await findByLabelText(/^Tasty Spot, ranked number 1/);
    fireEvent.press(row);
    expect(mockPush).toHaveBeenCalledWith('/place/p0');
  });

  it('does not let a stale response from a previous account overwrite the newly signed-in account\'s data', async () => {
    setAuthedUser({ id: 'user-A' });
    let resolveSlowA: (v: RankedPlace[]) => void;
    mockedFetchMyRankings.mockImplementationOnce(
      () => new Promise((resolve) => { resolveSlowA = resolve; }),
    );

    const { rerender, findByText } = render(<ProfileScreen />);
    // user-A's load() is now in flight, unresolved.

    // Switch accounts before it resolves -- a real re-focus/useEffect
    // re-fire for user-B, whose own fetch resolves immediately.
    setAuthedUser({ id: 'user-B' });
    mockedFetchMyRankings.mockResolvedValue([makeRanking('b-place', { name: 'B Place' })]);
    rerender(<ProfileScreen />);
    await findByText('One place ranked. The list begins.');

    // Now the stale user-A response lands late.
    await act(async () => {
      resolveSlowA!([makeRanking('a-place', { name: 'A Place' })]);
    });

    // The screen must still reflect user-B's data, not be clobbered by
    // user-A's late response.
    expect(await findByText('B Place')).toBeTruthy();
  });
});
