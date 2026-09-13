import React from 'react';
import { Alert } from 'react-native';
import { act, fireEvent, render } from '@testing-library/react-native';
import UserProfileScreen from '../app/user/[id]';
import { useAuthStore } from '../src/stores/authStore';
import { fetchBlockStatus, fetchFollowStatus, fetchProfile, followUser } from '../src/api/social';
import { requestAuthGate } from '../src/stores/authGateStore';

jest.mock('expo-router', () => ({
  useLocalSearchParams: () => ({ id: 'other' }),
  useFocusEffect: (cb: () => void) => require('react').useEffect(cb, [cb]),
}));
jest.mock('../src/stores/authStore', () => ({ useAuthStore: jest.fn() }));
jest.mock('../src/stores/authGateStore', () => ({ requestAuthGate: jest.fn() }));
jest.mock('../src/api/social', () => ({
  fetchProfile: jest.fn(), fetchFollowStatus: jest.fn(), fetchBlockStatus: jest.fn(),
  followUser: jest.fn(), unfollowUser: jest.fn(), blockUser: jest.fn(), unblockUser: jest.fn(),
}));
jest.mock('expo-haptics', () => ({ impactAsync: jest.fn(), ImpactFeedbackStyle: { Light: 'light', Medium: 'medium' } }));

const mockedAuth = useAuthStore as unknown as jest.Mock;
const mockedProfile = fetchProfile as jest.MockedFunction<typeof fetchProfile>;
const mockedFollowStatus = fetchFollowStatus as jest.MockedFunction<typeof fetchFollowStatus>;
const mockedBlockStatus = fetchBlockStatus as jest.MockedFunction<typeof fetchBlockStatus>;
const mockedFollow = followUser as jest.MockedFunction<typeof followUser>;
const mockedGate = requestAuthGate as jest.MockedFunction<typeof requestAuthGate>;

function setMe(id: string | null) {
  mockedAuth.mockImplementation((selector: (s: unknown) => unknown) => selector({ user: id ? { id } : null }));
}

describe('UserProfileScreen privacy and follow reliability', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(Alert, 'alert').mockImplementation(() => {});
    setMe('me');
    mockedProfile.mockResolvedValue({ id: 'other', username: 'alice', display_name: 'Alice', avatar_url: null, bio: null, is_public: true });
    mockedFollowStatus.mockResolvedValue({ following: false, followed_by: false });
    mockedBlockStatus.mockResolvedValue({ blocked: false });
  });

  it('shows public identity but never exact Rank or Taste data', async () => {
    const { findByText, queryByText } = render(<UserProfileScreen />);
    expect(await findByText('Alice')).toBeTruthy();
    expect(await findByText(/Ranked places and Taste Profile insights are private/)).toBeTruthy();
    expect(queryByText(/ranked number/)).toBeNull();
    expect(queryByText(/taste match/)).toBeNull();
  });

  it('preserves a signed-out follow intent through the shared auth gate', async () => {
    setMe(null);
    const { findByLabelText } = render(<UserProfileScreen />);
    fireEvent.press(await findByLabelText('Follow alice'));
    expect(mockedGate).toHaveBeenCalledWith(expect.objectContaining({
      actionType: 'follow-user', reason: 'follow', targetIds: ['other'], destination: '/user/other', idempotent: true,
    }));
    expect(mockedFollow).not.toHaveBeenCalled();
  });

  it('reverts and surfaces a failed follow write', async () => {
    mockedFollow.mockRejectedValue(new Error('server'));
    const { findByLabelText } = render(<UserProfileScreen />);
    const followButton = await findByLabelText('Follow alice');
    await act(async () => { fireEvent.press(followButton); });
    expect(await findByLabelText('Follow alice')).toBeTruthy();
    expect(Alert.alert).toHaveBeenCalledWith("Couldn't follow", 'Your change was not saved. Try again.');
  });
});
