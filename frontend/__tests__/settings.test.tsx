// Settings screen (app/settings.tsx) — first dedicated coverage. Locks
// in: city display, navigation rows, the two-step destructive-action
// confirm flows (sign out, delete account -- including delete's failure
// path leaving the user signed in), and the account section's
// signed-in-only visibility.
import React from 'react';
import { Alert, Linking } from 'react-native';
import { fireEvent, render } from '@testing-library/react-native';
import SettingsScreen from '../app/settings';
import { useCityStore } from '../src/stores/cityStore';
import { useAuthStore } from '../src/stores/authStore';
import { useVideoQueueStore, QueuedVideo } from '../src/stores/videoQueueStore';
import { usePostingDraftStore, PostingDraft } from '../src/stores/postingDraftStore';
import { deleteMyAccount } from '../src/api/social';

const mockPush = jest.fn();
jest.mock('expo-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useFocusEffect: (cb: () => void) => require('react').useEffect(cb, [cb]),
}));
jest.mock('../src/stores/authStore', () => ({
  useAuthStore: jest.fn(),
}));
jest.mock('../src/api/cities', () => ({
  fetchCities: jest.fn().mockResolvedValue([]),
}));
jest.mock('../src/api/social', () => ({
  deleteMyAccount: jest.fn(),
}));
jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  ImpactFeedbackStyle: { Light: 'light' },
}));

const mockGetPushPermissionStatus = jest.fn();
const mockRequestAndRegisterPush = jest.fn();
jest.mock('../src/services/pushNotifications', () => ({
  getPushPermissionStatus: (...args: unknown[]) => mockGetPushPermissionStatus(...args),
  requestAndRegisterPush: (...args: unknown[]) => mockRequestAndRegisterPush(...args),
}));

const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;
const mockedDeleteMyAccount = deleteMyAccount as jest.MockedFunction<typeof deleteMyAccount>;
const mockSignOut = jest.fn().mockResolvedValue(undefined);
const mockToastShow = jest.fn();

jest.mock('../src/hooks/useToast', () => ({
  useToast: (selector: (s: { show: (msg: string) => void }) => unknown) =>
    selector({ show: mockToastShow }),
}));

const SF_CITY = { id: 'city-sf', name: 'San Francisco', slug: 'san-francisco', lat: 37.7749, lng: -122.4194 };

function pressAlertButton(buttonText: string) {
  const call = (Alert.alert as jest.Mock).mock.calls[(Alert.alert as jest.Mock).mock.calls.length - 1];
  const buttons = call[2] as { text: string; onPress?: () => void }[];
  const button = buttons.find((b) => b.text === buttonText);
  button?.onPress?.();
}

describe('SettingsScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(Alert, 'alert').mockImplementation(() => {});
    jest.spyOn(Linking, 'openURL').mockResolvedValue(true);
    jest.spyOn(Linking, 'openSettings').mockResolvedValue(undefined);
    useCityStore.setState({ selectedCity: SF_CITY, cities: [SF_CITY] });
    useVideoQueueStore.setState({ videos: [] });
    usePostingDraftStore.setState({ drafts: [] });
    mockedUseAuthStore.mockImplementation((selector: (s: unknown) => unknown) =>
      selector({ user: { id: 'user-1', email: 'a@b.com' }, signOut: mockSignOut }),
    );
    mockGetPushPermissionStatus.mockResolvedValue('undetermined');
  });

  it('navigates to the Uploads screen, showing no count when nothing is pending', () => {
    const { getByText, getByLabelText } = render(<SettingsScreen />);
    expect(getByText('Queued and failed photo/video uploads')).toBeTruthy();

    fireEvent.press(getByLabelText('Uploads'));
    expect(mockPush).toHaveBeenCalledWith('/uploads');
  });

  it('shows a pending count combining this user\'s queued videos and drafts, excluding synced videos and other users\'', () => {
    const video: QueuedVideo = {
      id: 'v1', serverId: null, localUri: 'file:///v1.mp4', placeId: 'place-1', templateId: null,
      contentType: 'video/mp4', uploadedBy: 'user-1', syncState: 'failed', attemptCount: 5,
      lastAttemptAt: Date.now(), lastError: 'Network Error', createdAt: Date.now(),
    };
    const syncedVideo: QueuedVideo = { ...video, id: 'v2', syncState: 'synced' };
    const otherUserVideo: QueuedVideo = { ...video, id: 'v3', uploadedBy: 'someone-else' };
    useVideoQueueStore.setState({ videos: [video, syncedVideo, otherUserVideo] });

    const draft: PostingDraft = {
      id: 'd1', ownerId: 'user-1', localUri: 'file:///d1.jpg', kind: 'photo', mimeType: 'image/jpeg',
      fileSize: 100, restaurantRef: { type: 'unresolved' }, outcome: 'pending', lastError: null,
      createdAt: Date.now(),
    };
    const otherUserDraft: PostingDraft = { ...draft, id: 'd2', ownerId: 'someone-else' };
    usePostingDraftStore.setState({ drafts: [draft, otherUserDraft] });

    const { getByText } = render(<SettingsScreen />);
    // 1 failed video (not the synced or other-user one) + 1 draft = 2.
    expect(getByText('2 pending')).toBeTruthy();
  });

  it('shows the current city, and falls back to "None selected" when there is none', () => {
    const { getByText, rerender } = render(<SettingsScreen />);
    expect(getByText('San Francisco')).toBeTruthy();

    useCityStore.setState({ selectedCity: null, cities: [] });
    rerender(<SettingsScreen />);
    expect(getByText('None selected')).toBeTruthy();
  });

  it('shows the current notification permission status, re-checked on every focus', async () => {
    mockGetPushPermissionStatus.mockResolvedValue('granted');
    const { findByText } = render(<SettingsScreen />);
    expect(await findByText('Enabled — tap to manage in Settings')).toBeTruthy();
    expect(mockGetPushPermissionStatus).toHaveBeenCalled();
  });

  it('explains the benefit before requesting permission when not yet determined', async () => {
    mockGetPushPermissionStatus.mockResolvedValue('undetermined');
    mockRequestAndRegisterPush.mockResolvedValue('granted');
    const { findByLabelText, findByText } = render(<SettingsScreen />);
    expect(await findByText('Off — tap to turn on')).toBeTruthy();

    fireEvent.press(await findByLabelText('Notifications'));
    expect(Alert.alert).toHaveBeenCalledWith(
      'Enable notifications',
      expect.stringContaining('approved or rejected'),
      expect.any(Array),
    );
    expect(mockRequestAndRegisterPush).not.toHaveBeenCalled();

    pressAlertButton('Enable');
    await new Promise((r) => setTimeout(r, 0));
    expect(mockRequestAndRegisterPush).toHaveBeenCalledTimes(1);
    expect(await findByText('Enabled — tap to manage in Settings')).toBeTruthy();
  });

  it('opens OS Settings directly when already granted or denied, without re-prompting', async () => {
    mockGetPushPermissionStatus.mockResolvedValue('denied');
    const { findByLabelText } = render(<SettingsScreen />);

    fireEvent.press(await findByLabelText('Notifications'));

    expect(Alert.alert).not.toHaveBeenCalled();
    expect(mockRequestAndRegisterPush).not.toHaveBeenCalled();
    expect(Linking.openSettings).toHaveBeenCalledTimes(1);
  });

  it('is non-interactive when push is unavailable on this build', async () => {
    mockGetPushPermissionStatus.mockResolvedValue('unavailable');
    const { findByText, queryByLabelText } = render(<SettingsScreen />);
    expect(await findByText('Not available on this build')).toBeTruthy();
    expect(queryByLabelText('Notifications')).toBeNull();
  });

  it('navigates to add-spot, privacy, and terms', () => {
    const { getByLabelText } = render(<SettingsScreen />);
    fireEvent.press(getByLabelText('Add a new spot'));
    expect(mockPush).toHaveBeenCalledWith('/add-spot');

    fireEvent.press(getByLabelText('Privacy Policy'));
    expect(mockPush).toHaveBeenCalledWith('/legal/privacy');

    fireEvent.press(getByLabelText('Terms of Service'));
    expect(mockPush).toHaveBeenCalledWith('/legal/terms');
  });

  it('shows the native app/build version and explains CRAVE via an alert', () => {
    const { getByText, getByLabelText } = render(<SettingsScreen />);
    expect(getByText('mock (mock)')).toBeTruthy();

    fireEvent.press(getByLabelText('How CRAVE Works'));
    expect(Alert.alert).toHaveBeenCalledWith('How CRAVE Works', expect.stringContaining('CRAVE ranks restaurants'));
  });

  it('opens a mailto link for Send Feedback, and toasts if opening fails', async () => {
    const { getByLabelText } = render(<SettingsScreen />);
    fireEvent.press(getByLabelText('Send Feedback'));
    expect(Linking.openURL).toHaveBeenCalledWith(expect.stringContaining('mailto:hello@crave.app'));

    (Linking.openURL as jest.Mock).mockRejectedValueOnce(new Error('no handler'));
    fireEvent.press(getByLabelText('Send Feedback'));
    await new Promise((r) => setTimeout(r, 0));
    expect(mockToastShow).toHaveBeenCalledWith("Couldn't open that link.");
  });

  it('shows the account section only when signed in, with the account email as the label', () => {
    const { getByText, getByLabelText, queryByLabelText, rerender } = render(<SettingsScreen />);
    expect(getByText('a@b.com')).toBeTruthy();
    expect(getByLabelText('Sign Out')).toBeTruthy();

    mockedUseAuthStore.mockImplementation((selector: (s: unknown) => unknown) =>
      selector({ user: null, signOut: mockSignOut }),
    );
    rerender(<SettingsScreen />);
    expect(queryByLabelText('Sign Out')).toBeNull();
    expect(queryByLabelText('Delete Account')).toBeNull();
  });

  it('signs out only after confirming, not on the initial tap', () => {
    const { getByLabelText } = render(<SettingsScreen />);
    fireEvent.press(getByLabelText('Sign Out'));
    expect(mockSignOut).not.toHaveBeenCalled();

    pressAlertButton('Sign Out');
    expect(mockSignOut).toHaveBeenCalledTimes(1);
  });

  it('does not sign out on cancelling either confirmation step', () => {
    const { getByLabelText } = render(<SettingsScreen />);
    fireEvent.press(getByLabelText('Sign Out'));
    pressAlertButton('Cancel');
    expect(mockSignOut).not.toHaveBeenCalled();
  });

  it('deletes the account only after both confirmation steps, then signs out', async () => {
    mockedDeleteMyAccount.mockResolvedValue({} as any);
    const { getByLabelText } = render(<SettingsScreen />);

    fireEvent.press(getByLabelText('Delete Account'));
    expect(mockedDeleteMyAccount).not.toHaveBeenCalled();

    pressAlertButton('Delete Account');
    expect(mockedDeleteMyAccount).not.toHaveBeenCalled();

    pressAlertButton('Yes, delete everything');
    await new Promise((r) => setTimeout(r, 0));

    expect(mockedDeleteMyAccount).toHaveBeenCalledTimes(1);
    expect(mockSignOut).toHaveBeenCalledTimes(1);
  });

  it('leaves the user signed in and toasts an error if account deletion fails', async () => {
    mockedDeleteMyAccount.mockRejectedValue(new Error('server error'));
    const { getByLabelText } = render(<SettingsScreen />);

    fireEvent.press(getByLabelText('Delete Account'));
    pressAlertButton('Delete Account');
    pressAlertButton('Yes, delete everything');
    await new Promise((r) => setTimeout(r, 0));

    expect(mockToastShow).toHaveBeenCalledWith(
      "Couldn't complete account deletion. Your session is still active — try again.",
    );
    expect(mockSignOut).not.toHaveBeenCalled();
  });
});
