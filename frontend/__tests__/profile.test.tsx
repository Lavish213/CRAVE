import React from 'react';
import { act, fireEvent, render } from '@testing-library/react-native';
import ProfileScreen from '../app/(tabs)/profile';
import { useAuthStore } from '../src/stores/authStore';
import { fetchMyProfile, fetchMyRankings, fetchTasteProfile } from '../src/api/social';

const mockPush = jest.fn();
jest.mock('expo-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useFocusEffect: (cb: () => void) => require('react').useEffect(cb, [cb]),
}));
jest.mock('../src/stores/authStore', () => ({ useAuthStore: jest.fn() }));
jest.mock('../src/api/social', () => ({
  fetchMyProfile: jest.fn(), fetchMyRankings: jest.fn(), fetchTasteProfile: jest.fn(),
}));
jest.mock('../src/components/AuthSheet', () => {
  const { Text } = require('react-native');
  return {
    AuthSheet: ({ visible }: { visible: boolean }) =>
      visible ? <Text testID="auth-sheet-visible">auth</Text> : null,
  };
});

const mockedAuth = useAuthStore as unknown as jest.Mock;
const mockedProfile = fetchMyProfile as jest.MockedFunction<typeof fetchMyProfile>;
const mockedRankings = fetchMyRankings as jest.MockedFunction<typeof fetchMyRankings>;
const mockedTaste = fetchTasteProfile as jest.MockedFunction<typeof fetchTasteProfile>;

function setAuthedUser(user: { id: string } | null) {
  mockedAuth.mockImplementation((selector: (s: { user: unknown }) => unknown) => selector({ user }));
}

describe('ProfileScreen food identity', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setAuthedUser({ id: 'me' });
    mockedProfile.mockResolvedValue({ id: 'me', username: 'alice', display_name: 'Alice', avatar_url: null, bio: null, is_public: true });
    mockedRankings.mockResolvedValue([]);
    mockedTaste.mockResolvedValue({ total_ranked: 0, tier_counts: { liked: 0, fine: 0, disliked: 0 }, favorite_cuisine: null, top_city: null });
  });

  it('shows a sign-in prompt when signed out and opens AuthSheet', async () => {
    setAuthedUser(null);
    const { getByText, findByTestId } = render(<ProfileScreen />);
    expect(getByText('Sign in to build your food identity')).toBeTruthy();
    fireEvent.press(getByText('Sign in'));
    expect(await findByTestId('auth-sheet-visible')).toBeTruthy();
  });

  it('prompts to choose a username when signed in but no profile exists', async () => {
    mockedProfile.mockResolvedValue(null);
    const { findByText } = render(<ProfileScreen />);
    fireEvent.press(await findByText('Choose username'));
    expect(mockPush).toHaveBeenCalledWith('/profile-setup');
  });

  it('does not mistake a failed profile request for a missing username', async () => {
    // A bare network Error (no `.response`) is classified as a genuine
    // offline failure -- see errorMessageFor in src/utils/errorMessage.ts.
    mockedProfile.mockRejectedValue(new Error('network'));
    const { findByText, queryByText } = render(<ProfileScreen />);
    expect(await findByText("Can't reach CRAVE — check your connection.")).toBeTruthy();
    expect(queryByText('Pick a username')).toBeNull();
  });

  it('centers private food identity without vanity or legacy social links', async () => {
    const { findByText, findByLabelText, queryByText, queryByLabelText } = render(<ProfileScreen />);
    expect(await findByText(/CRAVE is still learning your taste/)).toBeTruthy();
    expect(queryByText('followers')).toBeNull();
    expect(queryByText('following')).toBeNull();
    expect(queryByLabelText('Friends activity')).toBeNull();
    expect(queryByLabelText('Leaderboard')).toBeNull();
    fireEvent.press(await findByLabelText('Open your private Taste Profile'));
    expect(mockPush).toHaveBeenCalledWith('/taste-profile/me');
  });

  it('routes Rank status to Rank Home', async () => {
    const { findByLabelText } = render(<ProfileScreen />);
    fireEvent.press(await findByLabelText('Open Rank'));
    expect(mockPush).toHaveBeenCalledWith('/rank-home');
  });

  it('does not turn a failed taste fetch into invented insight', async () => {
    mockedTaste.mockRejectedValue(new Error('offline'));
    const { findByText } = render(<ProfileScreen />);
    expect(await findByText('Your private Taste Profile is temporarily unavailable.')).toBeTruthy();
  });

  it('uses supported aggregates instead of qualitative ranking claims', async () => {
    mockedRankings.mockResolvedValue([
      { place_id: 'p1', name: 'One', tier: 'liked', rank_score: 8, note: null, tags: null, visited_at: null, primary_image_url: null, city_id: 'oak' },
      { place_id: 'p2', name: 'Two', tier: 'fine', rank_score: 5, note: null, tags: null, visited_at: null, primary_image_url: null, city_id: 'oak' },
    ]);
    mockedTaste.mockResolvedValue({
      total_ranked: 2,
      tier_counts: { liked: 1, fine: 1, disliked: 0 },
      favorite_cuisine: null,
      top_city: { id: 'oak', name: 'Oakland', count: 2 },
    });

    const { findByText, queryByText } = render(<ProfileScreen />);
    expect(await findByText('2 places ranked. Most of your food history is in Oakland.')).toBeTruthy();
    expect(queryByText(/You know what you like|Your list is taking shape/)).toBeNull();
  });

  it('clears the previous account state immediately on account switch', async () => {
    setAuthedUser({ id: 'user-A' });
    mockedProfile.mockResolvedValue({ id: 'user-A', username: 'alice', display_name: 'Alice', avatar_url: null, bio: null, is_public: true });
    const { rerender, findByText, queryByText } = render(<ProfileScreen />);
    expect(await findByText('Alice')).toBeTruthy();

    setAuthedUser({ id: 'user-B' });
    mockedProfile.mockImplementationOnce(() => new Promise(() => {}));
    mockedRankings.mockImplementationOnce(() => new Promise(() => {}));
    rerender(<ProfileScreen />);
    expect(queryByText('Alice')).toBeNull();
  });

  it('does not let a stale response from a previous account overwrite the new account', async () => {
    setAuthedUser({ id: 'user-A' });
    mockedProfile.mockResolvedValue({ id: 'user-A', username: 'alice', display_name: 'Alice', avatar_url: null, bio: null, is_public: true });
    let resolveSlowA: (v: { id: string; username: string; display_name: string; avatar_url: null; bio: null; is_public: boolean }) => void;
    mockedProfile.mockImplementationOnce(
      () => new Promise((resolve) => { resolveSlowA = resolve; }),
    );
    const { rerender, findByText } = render(<ProfileScreen />);

    setAuthedUser({ id: 'user-B' });
    mockedProfile.mockResolvedValue({ id: 'user-B', username: 'bob', display_name: 'Bob', avatar_url: null, bio: null, is_public: true });
    rerender(<ProfileScreen />);
    expect(await findByText('Bob')).toBeTruthy();

    await act(async () => {
      resolveSlowA!({ id: 'user-A', username: 'alice', display_name: 'Alice', avatar_url: null, bio: null, is_public: true });
    });

    expect(await findByText('Bob')).toBeTruthy();
  });
});
