import React from 'react';
import { fireEvent, render } from '@testing-library/react-native';
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
jest.mock('../src/components/AuthSheet', () => ({ AuthSheet: () => null }));

const mockedAuth = useAuthStore as unknown as jest.Mock;
const mockedProfile = fetchMyProfile as jest.MockedFunction<typeof fetchMyProfile>;
const mockedRankings = fetchMyRankings as jest.MockedFunction<typeof fetchMyRankings>;
const mockedTaste = fetchTasteProfile as jest.MockedFunction<typeof fetchTasteProfile>;

describe('ProfileScreen food identity', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedAuth.mockImplementation((selector: (s: unknown) => unknown) => selector({ user: { id: 'me' } }));
    mockedProfile.mockResolvedValue({ id: 'me', username: 'alice', display_name: 'Alice', avatar_url: null, bio: null, is_public: true });
    mockedRankings.mockResolvedValue([]);
    mockedTaste.mockResolvedValue({ total_ranked: 0, tier_counts: { liked: 0, fine: 0, disliked: 0 }, favorite_cuisine: null, top_city: null });
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
});
