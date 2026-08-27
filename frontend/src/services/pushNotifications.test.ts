// Regression coverage for src/services/pushNotifications.ts -- the real
// push lifecycle (status, contextual request, silent re-registration,
// unregister-on-sign-out). Mirrors this repo's other hook/store test
// mocking conventions (see cravesStore.test.ts, videoQueueStore.test.ts).
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
  unregisterPushToken: jest.fn(),
}));

import * as Notifications from 'expo-notifications';
import Constants from 'expo-constants';
import { registerPushToken, unregisterPushToken } from '../api/account';
import {
  getPushPermissionStatus,
  requestAndRegisterPush,
  silentlyReregisterIfGranted,
  unregisterCurrentDevice,
} from './pushNotifications';

describe('pushNotifications service', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // @ts-expect-error -- mutating the jest.mock()'d module's plain object directly
    Constants.expoConfig = { extra: { eas: { projectId: 'test-project-id' } } };
  });

  describe('getPushPermissionStatus', () => {
    it('reports unavailable when no EAS projectId is configured', async () => {
      // @ts-expect-error -- same mutation as above
      Constants.expoConfig = { extra: { eas: {} } };
      expect(await getPushPermissionStatus()).toBe('unavailable');
      expect(Notifications.getPermissionsAsync).not.toHaveBeenCalled();
    });

    it('passes through the real OS status when available', async () => {
      (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({ status: 'denied' });
      expect(await getPushPermissionStatus()).toBe('denied');
    });
  });

  describe('requestAndRegisterPush', () => {
    it('requests permission when not already determined, and registers if allowed', async () => {
      (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({ status: 'undetermined' });
      (Notifications.requestPermissionsAsync as jest.Mock).mockResolvedValue({ status: 'granted' });
      (Notifications.getExpoPushTokenAsync as jest.Mock).mockResolvedValue({
        data: 'ExponentPushToken[xyz789]',
      });

      const result = await requestAndRegisterPush();

      expect(result).toBe('granted');
      expect(registerPushToken).toHaveBeenCalledWith('ExponentPushToken[xyz789]', expect.any(String));
    });

    it('does not register a token when the user denies the prompt', async () => {
      (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({ status: 'undetermined' });
      (Notifications.requestPermissionsAsync as jest.Mock).mockResolvedValue({ status: 'denied' });

      const result = await requestAndRegisterPush();

      expect(result).toBe('denied');
      expect(Notifications.getExpoPushTokenAsync).not.toHaveBeenCalled();
      expect(registerPushToken).not.toHaveBeenCalled();
    });

    it('does not re-prompt when permission was already granted', async () => {
      (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({ status: 'granted' });
      (Notifications.getExpoPushTokenAsync as jest.Mock).mockResolvedValue({
        data: 'ExponentPushToken[abc123]',
      });

      await requestAndRegisterPush();

      expect(Notifications.requestPermissionsAsync).not.toHaveBeenCalled();
      expect(registerPushToken).toHaveBeenCalledWith('ExponentPushToken[abc123]', expect.any(String));
    });

    it('returns unavailable without calling any Notifications API when there is no EAS projectId', async () => {
      // @ts-expect-error -- same mutation as above
      Constants.expoConfig = { extra: { eas: {} } };
      const result = await requestAndRegisterPush();
      expect(result).toBe('unavailable');
      expect(Notifications.getPermissionsAsync).not.toHaveBeenCalled();
    });
  });

  describe('silentlyReregisterIfGranted', () => {
    it('registers the token when permission is already granted, without prompting', async () => {
      (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({ status: 'granted' });
      (Notifications.getExpoPushTokenAsync as jest.Mock).mockResolvedValue({
        data: 'ExponentPushToken[abc123]',
      });

      await silentlyReregisterIfGranted();

      expect(Notifications.requestPermissionsAsync).not.toHaveBeenCalled();
      expect(registerPushToken).toHaveBeenCalledWith('ExponentPushToken[abc123]', expect.any(String));
    });

    it('does nothing when permission has not been granted yet', async () => {
      (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({ status: 'undetermined' });

      await silentlyReregisterIfGranted();

      expect(Notifications.requestPermissionsAsync).not.toHaveBeenCalled();
      expect(Notifications.getExpoPushTokenAsync).not.toHaveBeenCalled();
      expect(registerPushToken).not.toHaveBeenCalled();
    });

    it('does not throw when registerPushToken itself fails', async () => {
      (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({ status: 'granted' });
      (Notifications.getExpoPushTokenAsync as jest.Mock).mockResolvedValue({
        data: 'ExponentPushToken[abc123]',
      });
      (registerPushToken as jest.Mock).mockRejectedValue(new Error('network error'));

      await expect(silentlyReregisterIfGranted()).resolves.toBeUndefined();
    });
  });

  describe('unregisterCurrentDevice', () => {
    it('unregisters the current token when permission is granted', async () => {
      (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({ status: 'granted' });
      (Notifications.getExpoPushTokenAsync as jest.Mock).mockResolvedValue({
        data: 'ExponentPushToken[abc123]',
      });

      await unregisterCurrentDevice();

      expect(unregisterPushToken).toHaveBeenCalledWith('ExponentPushToken[abc123]');
    });

    it('does nothing when permission was never granted (nothing to unregister)', async () => {
      (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({ status: 'undetermined' });

      await unregisterCurrentDevice();

      expect(Notifications.getExpoPushTokenAsync).not.toHaveBeenCalled();
      expect(unregisterPushToken).not.toHaveBeenCalled();
    });

    it('does not throw when unregisterPushToken itself fails -- must never block sign-out', async () => {
      (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({ status: 'granted' });
      (Notifications.getExpoPushTokenAsync as jest.Mock).mockResolvedValue({
        data: 'ExponentPushToken[abc123]',
      });
      (unregisterPushToken as jest.Mock).mockRejectedValue(new Error('network error'));

      await expect(unregisterCurrentDevice()).resolves.toBeUndefined();
    });
  });
});
