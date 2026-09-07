import React from 'react';
import { act, fireEvent, render } from '@testing-library/react-native';
import ProfileScreen from '../app/(tabs)/profile';
import { useAuthStore } from '../src/stores/authStore';
import {
  Profile, RankedPlace, fetchFollowers, fetchFollowing, fetchMyProfile, fetchMyRankings,
} from '../src/api/social';
import { fetchMyStreak } from '../src/api/streak';

const mockPush = jest.fn();
jest.mock('expo-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useFocusEffect: (cb: () => void) => require('react').useEffect(cb, [cb]),
}));
jest.mock('../src/stores/authStore', () => ({ useAuthStore: jest.fn() }));
jest.mock('../src/api/social', () => ({
  fetchMyProfile: jest.fn(),
  fetchMyRankings: jest.fn(),
  fetchFollowing: jest.fn(),
  fetchFollowers: jest.fn(),
}));
jest.mock('../src/api/streak', () => ({ fetchMyStreak: jest.fn() }));
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

  it('shows a sign-in prompt when signed out and opens AuthSheet', async () => {
    setAuthedUser(null);
    const { getByText, findByTestId } = render(<ProfileScreen />);
    expect(getByText('Sign in to build your food identity')).toBeTruthy();
    fireEvent.press(getByText('Sign in'));
    expect(await findByTestId('auth-sheet-visible')).toBeTruthy();
  });

  it('prompts to choose a username when signed in but no profile exists', async () => {
    setAuthedUser({ id: 'user-1' });
    mockedFetchMyProfile.mockResolvedValue(null);
    const { findByText } = render(<ProfileScreen />);
    fireEvent.press(await findByText('Choose username'));
    expect(mockPush).toHaveBeenCalledWith('/profile-setup');
  });

  it('does not mistake a failed profile request for a missing username', async () => {
    setAuthedUser({ id: 'user-1' });
    mockedFetchMyProfile.mockRejectedValue(new Error('network'));
    const { findByText, queryByText } = render(<ProfileScreen />);
    expect(await findByText("Couldn't load your profile")).toBeTruthy();
    expect(queryByText('Pick a username')).toBeNull();
  });

  it('renders identity, compact Rank status, and below-threshold guidance', async () => {
    setAuthedUser({ id: 'user-1' });
    mockedFetchMyRankings.mockResolvedValue([makeRanking('p0'), makeRanking('p1')]);
    mockedFetchFollowing.mockResolvedValue(['f1']);
    mockedFetchFollowers.mockResolvedValue(['f1', 'f2']);

    const { findByText, findByLabelText, queryByText } = render(<ProfileScreen />);
    expect(await findByText('Alice')).toBeTruthy();
    expect(await findByText('@alice')).toBeTruthy();
    expect(await findByText(/2 places ranked/)).toBeTruthy();
    expect(await findByText(/Rank 13 more places/)).toBeTruthy();
    expect(await findByLabelText('Open Rank')).toBeTruthy();
    expect(queryByText('Your list')).toBeNull();
    expect(queryByText('p0')).toBeNull();
  });

  it('routes compact Rank ownership to Rank Home', async () => {
    setAuthedUser({ id: 'user-1' });
    mockedFetchMyRankings.mockResolvedValue([makeRanking('p0')]);
    const { findByLabelText } = render(<ProfileScreen />);
    fireEvent.press(await findByLabelText('Open Rank'));
    expect(mockPush).toHaveBeenCalledWith('/rank-home');
  });

  it('shows the Taste Profile link only when ranking evidence exists', async () => {
    setAuthedUser({ id: 'user-1' });
    const empty = render(<ProfileScreen />);
    await empty.findByText('Alice');
    expect(empty.queryByLabelText('Your Taste Profile')).toBeNull();
    empty.unmount();

    mockedFetchMyRankings.mockResolvedValue([makeRanking('p0')]);
    const populated = render(<ProfileScreen />);
    expect(await populated.findByLabelText('Your Taste Profile')).toBeTruthy();
  });

  it('shows the streak tile when current_streak is positive and hides rank guidance at threshold', async () => {
    setAuthedUser({ id: 'user-1' });
    mockedFetchMyRankings.mockResolvedValue(Array.from({ length: 15 }, (_, i) => makeRanking(`p${i}`)));
    mockedFetchMyStreak.mockResolvedValue({ current_streak: 99, longest_streak: 99, last_active_date: '2026-09-06' });
    const { findByText, queryByText } = render(<ProfileScreen />);
    expect(await findByText('99')).toBeTruthy();
    expect(await findByText('day streak')).toBeTruthy();
    expect(queryByText(/Rank .* more places/)).toBeNull();
  });

  it('shows unavailable stats instead of false zeroes when reads fail', async () => {
    setAuthedUser({ id: 'user-1' });
    mockedFetchMyRankings.mockRejectedValue(new Error('network'));
    mockedFetchFollowing.mockRejectedValue(new Error('network'));
    mockedFetchFollowers.mockRejectedValue(new Error('network'));
    mockedFetchMyStreak.mockRejectedValue(new Error('network'));
    const { findAllByText, findByText } = render(<ProfileScreen />);
    expect((await findAllByText('—')).length).toBe(4);
    expect(await findByText('day streak')).toBeTruthy();
  });

  it('clears the previous account state immediately on account switch', async () => {
    setAuthedUser({ id: 'user-A' });
    mockedFetchMyRankings.mockResolvedValue([makeRanking('a-place')]);
    const { rerender, findByText, queryByText } = render(<ProfileScreen />);
    expect(await findByText('One place ranked. The list begins.')).toBeTruthy();

    setAuthedUser({ id: 'user-B' });
    mockedFetchMyProfile.mockImplementationOnce(() => new Promise(() => {}));
    mockedFetchMyRankings.mockImplementationOnce(() => new Promise(() => {}));
    rerender(<ProfileScreen />);
    expect(queryByText('Alice')).toBeNull();
    expect(queryByText('One place ranked. The list begins.')).toBeNull();
  });

  it('does not let a stale response from a previous account overwrite the new account', async () => {
    setAuthedUser({ id: 'user-A' });
    let resolveSlowA: (v: RankedPlace[]) => void;
    mockedFetchMyRankings.mockImplementationOnce(
      () => new Promise((resolve) => { resolveSlowA = resolve; }),
    );
    const { rerender, findByText } = render(<ProfileScreen />);

    setAuthedUser({ id: 'user-B' });
    mockedFetchMyRankings.mockResolvedValue([makeRanking('b-place')]);
    rerender(<ProfileScreen />);
    expect(await findByText('One place ranked. The list begins.')).toBeTruthy();

    await act(async () => {
      resolveSlowA!([makeRanking('a-place'), makeRanking('a-place-2')]);
    });

    expect(await findByText('One place ranked. The list begins.')).toBeTruthy();
  });
});
