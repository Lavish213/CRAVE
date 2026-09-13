import React from 'react';
import { render } from '@testing-library/react-native';
import TasteProfileScreen from '../app/taste-profile/[userId]';
import { useAuthStore } from '../src/stores/authStore';
import { fetchProfile, fetchTasteProfile } from '../src/api/social';

let mockUserId = 'me';
jest.mock('expo-router', () => ({
  useLocalSearchParams: () => ({ userId: mockUserId }),
  useFocusEffect: (cb: () => void) => require('react').useEffect(cb, [cb]),
}));
jest.mock('../src/stores/authStore', () => ({ useAuthStore: jest.fn() }));
jest.mock('../src/api/social', () => ({ fetchProfile: jest.fn(), fetchTasteProfile: jest.fn() }));

const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;
const mockedFetchProfile = fetchProfile as jest.MockedFunction<typeof fetchProfile>;
const mockedFetchTaste = fetchTasteProfile as jest.MockedFunction<typeof fetchTasteProfile>;

function setMe(id: string | null) {
  mockedUseAuthStore.mockImplementation((selector: (s: unknown) => unknown) =>
    selector({ user: id ? { id } : null }),
  );
}

describe('TasteProfileScreen privacy', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUserId = 'me';
    setMe('me');
    mockedFetchProfile.mockResolvedValue({ id: 'me', username: 'alice', display_name: 'Alice', avatar_url: null, bio: null, is_public: true });
    mockedFetchTaste.mockResolvedValue({
      total_ranked: 12,
      tier_counts: { liked: 7, fine: 3, disliked: 2 },
      favorite_cuisine: null,
      top_city: { id: 'sf', name: 'San Francisco', count: 8 },
    });
  });

  it('shows only factual owner aggregates and an honest learning state', async () => {
    const { findByText, queryByText } = render(<TasteProfileScreen />);
    expect(await findByText('Your Taste Profile')).toBeTruthy();
    expect(await findByText('Still learning')).toBeTruthy();
    expect(await findByText('San Francisco · 8 ranked')).toBeTruthy();
    expect(queryByText(/Top \d+%/)).toBeNull();
    expect(queryByText(/taste match/)).toBeNull();
  });

  it('does not fetch or render another user\'s private Taste Profile', async () => {
    mockUserId = 'other';
    const { findByText } = render(<TasteProfileScreen />);
    expect(await findByText('Taste Profile is private')).toBeTruthy();
    expect(mockedFetchProfile).not.toHaveBeenCalled();
    expect(mockedFetchTaste).not.toHaveBeenCalled();
  });

  it('distinguishes a failed owner fetch from an empty profile', async () => {
    mockedFetchTaste.mockRejectedValue(new Error('network'));
    const { findByText } = render(<TasteProfileScreen />);
    expect(await findByText("Couldn't load taste profile")).toBeTruthy();
  });
});
