// Regression coverage for usePushNotifications.ts -- now a thin wrapper
// around services/pushNotifications.silentlyReregisterIfGranted(). The
// permission/registration logic itself is covered in
// src/services/pushNotifications.test.ts.
import { renderHook } from '@testing-library/react-native';

jest.mock('../services/pushNotifications', () => ({
  silentlyReregisterIfGranted: jest.fn(),
}));

import { silentlyReregisterIfGranted } from '../services/pushNotifications';
import { usePushNotifications } from './usePushNotifications';

const mockedReregister = silentlyReregisterIfGranted as jest.Mock;

describe('usePushNotifications', () => {
  beforeEach(() => {
    mockedReregister.mockReset();
    mockedReregister.mockResolvedValue(undefined);
  });

  it('does nothing when no user is signed in', () => {
    renderHook(() => usePushNotifications(null));
    expect(mockedReregister).not.toHaveBeenCalled();
  });

  it('silently re-registers when a user is signed in', () => {
    renderHook(() => usePushNotifications('user-a'));
    expect(mockedReregister).toHaveBeenCalledTimes(1);
  });

  it('does not throw when re-registration itself fails', async () => {
    mockedReregister.mockRejectedValue(new Error('network error'));
    expect(() => renderHook(() => usePushNotifications('user-a'))).not.toThrow();
    await Promise.resolve();
  });
});
