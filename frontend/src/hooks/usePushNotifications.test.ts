// Regression coverage for usePushNotifications.ts -- registering this
// device's Expo push token with the backend once a user is signed in.
// Mirrors this repo's other hook/store test mocking conventions (see
// cravesStore.test.ts, videoQueueStore.test.ts).
import { renderHook, waitFor } from '@testing-library/react-native';

jest.mock('expo-notifications', () => ({
  getPermissionsAsync: jest.fn(),
  requestPermissionsAsync: jest.fn(),
  getExpoPushTokenAsync: jest.fn(),
}));

jest.mock('expo-constants', () => ({
  __esModule: true,
  default: { expoConfig: { extra: { eas: { projectId: 'test-project-id' } } } },
}));

jest.mock('../api/account', () => ({
  registerPushToken: jest.fn(),
}));

import * as Notifications from 'expo-notifications';
import Constants from 'expo-constants';
import { registerPushToken } from '../api/account';
import { usePushNotifications } from './usePushNotifications';

describe('usePushNotifications', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // @ts-expect-error -- mutating the jest.mock()'d module's plain object directly
    Constants.expoConfig = { extra: { eas: { projectId: 'test-project-id' } } };
  });

  it('does nothing when no EAS projectId is configured', async () => {
    // @ts-expect-error -- same mutation as above
    Constants.expoConfig = { extra: { eas: {} } };
    (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({ status: 'granted' });

    renderHook(() => usePushNotifications('user-a'));
    await Promise.resolve();
    await Promise.resolve();

    expect(Notifications.getPermissionsAsync).not.toHaveBeenCalled();
    expect(registerPushToken).not.toHaveBeenCalled();
  });

  it('does nothing when no user is signed in', async () => {
    renderHook(() => usePushNotifications(null));
    await Promise.resolve();

    expect(Notifications.getPermissionsAsync).not.toHaveBeenCalled();
    expect(registerPushToken).not.toHaveBeenCalled();
  });

  it('registers the token when permission is already granted', async () => {
    (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({ status: 'granted' });
    (Notifications.getExpoPushTokenAsync as jest.Mock).mockResolvedValue({
      data: 'ExponentPushToken[abc123]',
    });

    renderHook(() => usePushNotifications('user-a'));

    await waitFor(() => {
      expect(registerPushToken).toHaveBeenCalledWith('ExponentPushToken[abc123]', expect.any(String));
    });
    expect(Notifications.requestPermissionsAsync).not.toHaveBeenCalled();
  });

  it('requests permission when not already granted, and registers if the user allows it', async () => {
    (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({ status: 'undetermined' });
    (Notifications.requestPermissionsAsync as jest.Mock).mockResolvedValue({ status: 'granted' });
    (Notifications.getExpoPushTokenAsync as jest.Mock).mockResolvedValue({
      data: 'ExponentPushToken[xyz789]',
    });

    renderHook(() => usePushNotifications('user-a'));

    await waitFor(() => {
      expect(registerPushToken).toHaveBeenCalledWith('ExponentPushToken[xyz789]', expect.any(String));
    });
  });

  it('does not register a token when permission is denied', async () => {
    (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({ status: 'undetermined' });
    (Notifications.requestPermissionsAsync as jest.Mock).mockResolvedValue({ status: 'denied' });

    renderHook(() => usePushNotifications('user-a'));
    await Promise.resolve();
    await Promise.resolve();

    expect(Notifications.getExpoPushTokenAsync).not.toHaveBeenCalled();
    expect(registerPushToken).not.toHaveBeenCalled();
  });

  it('does not throw when registerPushToken itself fails', async () => {
    (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({ status: 'granted' });
    (Notifications.getExpoPushTokenAsync as jest.Mock).mockResolvedValue({
      data: 'ExponentPushToken[abc123]',
    });
    (registerPushToken as jest.Mock).mockRejectedValue(new Error('network error'));

    renderHook(() => usePushNotifications('user-a'));

    await waitFor(() => {
      expect(registerPushToken).toHaveBeenCalled();
    });
    // No assertion beyond "this didn't throw" -- registration failures
    // must never be user-visible or crash the app (see the hook's own
    // top-level try/catch).
  });
});
