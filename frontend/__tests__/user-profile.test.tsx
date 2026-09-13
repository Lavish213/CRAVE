import React from 'react';
import { Alert } from 'react-native';
import { act, fireEvent, render } from '@testing-library/react-native';
import UserProfileScreen from '../app/user/[id]';
import { useAuthStore } from '../src/stores/authStore';
import { fetchBlockStatus, fetchFollowStatus, fetchProfile, followUser, unfollowUser, blockUser, unblockUser } from '../src/api/social';
import { requestAuthGate } from '../src/stores/authGateStore';

let mockId = 'other';
jest.mock('expo-router', () => ({
  useLocalSearchParams: () => ({ id: mockId }),
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
const mockedUnfollow = unfollowUser as jest.MockedFunction<typeof unfollowUser>;
const mockedBlock = blockUser as jest.MockedFunction<typeof blockUser>;
const mockedUnblock = unblockUser as jest.MockedFunction<typeof unblockUser>;
const mockedGate = requestAuthGate as jest.MockedFunction<typeof requestAuthGate>;

function setMe(id: string | null) {
  mockedAuth.mockImplementation((selector: (s: unknown) => unknown) => selector({ user: id ? { id } : null }));
}

function pressAlertButton(buttonText: string) {
  const calls = (Alert.alert as jest.Mock).mock.calls;
  const call = calls[calls.length - 1];
  const buttons = call[2] as { text: string; onPress?: () => void }[];
  buttons.find((b) => b.text === buttonText)?.onPress?.();
}

describe('UserProfileScreen privacy and follow reliability', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(Alert, 'alert').mockImplementation(() => {});
    mockId = 'other';
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

  it('shows "Profile not found" on a 404', async () => {
    mockedProfile.mockRejectedValue({ response: { status: 404 } });
    const { findByText } = render(<UserProfileScreen />);
    expect(await findByText('Profile not found')).toBeTruthy();
  });

  it('does not describe a network/5xx failure on the profile fetch as a nonexistent account', async () => {
    // A bare network Error (no `.response`) is classified as a genuine
    // offline failure -- see errorMessageFor in src/utils/errorMessage.ts.
    mockedProfile.mockRejectedValue(new Error('network'));
    const { findByText, queryByText } = render(<UserProfileScreen />);
    expect(await findByText("Can't reach CRAVE — check your connection.")).toBeTruthy();
    expect(queryByText('Profile not found')).toBeNull();
  });

  it('recovers on retry after a transient profile-fetch failure, instead of staying stuck on the error', async () => {
    mockedProfile.mockRejectedValueOnce(new Error('network'));
    const { findByText, findByLabelText, queryByText } = render(<UserProfileScreen />);
    expect(await findByText("Can't reach CRAVE — check your connection.")).toBeTruthy();

    mockedProfile.mockResolvedValue({ id: 'other', username: 'alice', display_name: 'Alice', avatar_url: null, bio: null, is_public: true });
    await act(async () => {
      fireEvent.press(await findByLabelText('Try again'));
    });

    expect(await findByText('Alice')).toBeTruthy();
    expect(queryByText("Can't reach CRAVE — check your connection.")).toBeNull();
  });

  it('hides the follow button and options menu on your own profile', async () => {
    mockId = 'me';
    mockedProfile.mockResolvedValue({ id: 'me', username: 'alice', display_name: 'Alice', avatar_url: null, bio: null, is_public: true });

    const { findByText, queryByLabelText } = render(<UserProfileScreen />);
    await findByText('Alice');
    expect(queryByLabelText('Follow alice')).toBeNull();
    expect(queryByLabelText('More options')).toBeNull();
    // Self view never checks follow/block status against yourself.
    expect(mockedFollowStatus).not.toHaveBeenCalled();
    expect(mockedBlockStatus).not.toHaveBeenCalled();
  });

  it('shows the "Follows you" badge when they follow you back', async () => {
    mockedFollowStatus.mockResolvedValue({ following: false, followed_by: true });
    const { findByText } = render(<UserProfileScreen />);
    expect(await findByText('Follows you')).toBeTruthy();
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

  it('follows optimistically, and reverts with an alert if the request fails', async () => {
    mockedFollow.mockRejectedValue(new Error('server error'));
    const { findByLabelText } = render(<UserProfileScreen />);
    const followBtn = await findByLabelText('Follow alice');
    await act(async () => { fireEvent.press(followBtn); });
    expect(await findByLabelText('Follow alice')).toBeTruthy();
    expect(Alert.alert).toHaveBeenCalledWith("Couldn't follow", 'Your change was not saved. Try again.');
  });

  it('unfollows on tapping an already-following button', async () => {
    mockedFollowStatus.mockResolvedValue({ following: true, followed_by: false });
    mockedUnfollow.mockResolvedValue(undefined as any);

    const { findByLabelText } = render(<UserProfileScreen />);
    const unfollowBtn = await findByLabelText('Unfollow alice');
    await act(async () => { fireEvent.press(unfollowBtn); });

    expect(mockedUnfollow).toHaveBeenCalledWith('other');
    expect(await findByLabelText('Follow alice')).toBeTruthy();
  });

  it('blocks through the two-step options-menu confirm, and immediately clears follow state both ways', async () => {
    mockedFollowStatus.mockResolvedValue({ following: true, followed_by: true });
    mockedBlock.mockResolvedValue(undefined as any);

    const { findByLabelText, findByText, queryByLabelText } = render(<UserProfileScreen />);
    await findByLabelText('Unfollow alice');

    fireEvent.press(await findByLabelText('More options'));
    pressAlertButton('Block user');
    expect(mockedBlock).not.toHaveBeenCalled();

    await act(async () => { pressAlertButton('Block'); });

    expect(mockedBlock).toHaveBeenCalledWith('other');
    expect(await findByText("You've blocked @alice. Their activity is hidden from you.")).toBeTruthy();
    expect(queryByLabelText('Unfollow alice')).toBeNull();
    expect(queryByLabelText('Follows you')).toBeNull();
  });

  it('unblocks from the inline link on the blocked notice', async () => {
    mockedBlockStatus.mockResolvedValue({ blocked: true });
    mockedUnblock.mockResolvedValue(undefined as any);

    const { findByText, queryByText } = render(<UserProfileScreen />);
    const unblockLink = await findByText('Unblock');
    await act(async () => { fireEvent.press(unblockLink); });

    expect(mockedUnblock).toHaveBeenCalledWith('other');
    expect(queryByText("You've blocked @alice. Their activity is hidden from you.")).toBeNull();
  });

  it('shows an alert if blocking fails, without marking them blocked', async () => {
    mockedBlock.mockRejectedValue(new Error('server error'));

    const { findByLabelText, queryByText } = render(<UserProfileScreen />);
    fireEvent.press(await findByLabelText('More options'));
    pressAlertButton('Block user');
    await act(async () => { pressAlertButton('Block'); });

    expect(Alert.alert).toHaveBeenCalledWith("Couldn't block", 'Something went wrong. Try again.');
    expect(queryByText("You've blocked @alice. Their activity is hidden from you.")).toBeNull();
  });

  it('hides relationship actions when their status cannot be verified', async () => {
    mockedFollowStatus.mockRejectedValue(new Error('network'));

    const { findByText, queryByLabelText } = render(<UserProfileScreen />);

    expect(await findByText("Can't reach CRAVE — check your connection.")).toBeTruthy();
    expect(queryByLabelText('Follow alice')).toBeNull();
    expect(queryByLabelText('More options')).toBeNull();
  });

  it('clears the previous person\'s data immediately on an id change, before the new person\'s fetch resolves', async () => {
    const { rerender, findByText, queryByText } = render(<UserProfileScreen />);
    expect(await findByText('Alice')).toBeTruthy();

    mockId = 'yet-another';
    mockedProfile.mockImplementationOnce(() => new Promise(() => {}));
    rerender(<UserProfileScreen />);

    expect(queryByText('Alice')).toBeNull();
  });

  it('does not let a stale response from a previous id render under the new route', async () => {
    let resolveOld: (p: { id: string; username: string; display_name: string; avatar_url: null; bio: null; is_public: boolean }) => void;
    mockedProfile.mockImplementationOnce(
      () => new Promise((resolve) => { resolveOld = resolve; }),
    );

    const { rerender, findByText, queryByText } = render(<UserProfileScreen />);

    mockId = 'yet-another';
    mockedProfile.mockResolvedValue({ id: 'yet-another', username: 'newperson', display_name: 'New Person', avatar_url: null, bio: null, is_public: true });
    rerender(<UserProfileScreen />);
    await findByText('New Person');

    await act(async () => {
      resolveOld!({ id: 'other', username: 'alice', display_name: 'Stale Person', avatar_url: null, bio: null, is_public: true });
    });
    expect(queryByText('Stale Person')).toBeNull();
    expect(await findByText('New Person')).toBeTruthy();
  });
});
