jest.mock('@react-native-async-storage/async-storage', () => ({
  __esModule: true,
  default: {
    getItem: jest.fn(() => Promise.resolve(null)),
    setItem: jest.fn(() => Promise.resolve()),
    removeItem: jest.fn(() => Promise.resolve()),
  },
}));

import { useUploadPreferencesStore } from './uploadPreferencesStore';

describe('uploadPreferencesStore', () => {
  it('defaults Wi-Fi-only video uploads to off', () => {
    expect(useUploadPreferencesStore.getState().wifiOnlyVideoUploads).toBe(false);
  });

  it('setWifiOnlyVideoUploads updates the preference', () => {
    useUploadPreferencesStore.getState().setWifiOnlyVideoUploads(true);
    expect(useUploadPreferencesStore.getState().wifiOnlyVideoUploads).toBe(true);

    useUploadPreferencesStore.getState().setWifiOnlyVideoUploads(false);
    expect(useUploadPreferencesStore.getState().wifiOnlyVideoUploads).toBe(false);
  });
});
