import React from 'react';
import { fireEvent, render } from '@testing-library/react-native';
import { ErrorBoundary } from '../app/_layout';

// RootLayout imports several app-wide native/service modules that are not
// relevant to the boundary component itself. Keep this regression narrow:
// it proves the visible Retry delegates to Expo Router's framework-owned
// `retry` callback rather than toggling a private boolean like the old class
// boundary did.
jest.mock('expo-notifications', () => ({
  setNotificationHandler: jest.fn(),
  getLastNotificationResponseAsync: jest.fn().mockResolvedValue(null),
  addNotificationResponseReceivedListener: jest.fn(() => ({ remove: jest.fn() })),
}));
jest.mock('../src/hooks/usePushNotifications', () => ({ usePushNotifications: jest.fn() }));
jest.mock('../src/lib/supabase', () => ({ isSupabaseConfigured: true }));
jest.mock('../src/lib/queryClient', () => ({ queryClient: {} }));
jest.mock('../src/stores/cityStore', () => ({ useCityStore: jest.fn() }));
jest.mock('../src/stores/authStore', () => ({ useAuthStore: jest.fn() }));
jest.mock('../src/stores/cravesStore', () => ({ useCravesStore: jest.fn() }));
jest.mock('../src/stores/videoQueueStore', () => ({
  useVideoQueueStore: jest.fn(),
  setActiveUserForVideoSync: jest.fn(),
}));
jest.mock('../src/api/streak', () => ({ pingStreak: jest.fn() }));
jest.mock('../src/components/Toast', () => ({ ToastContainer: () => null }));

describe('root ErrorBoundary', () => {
  it('delegates Try again to Expo Router retry()', () => {
    const retry = jest.fn();
    const { getByLabelText } = render(
      <ErrorBoundary error={new Error('boom')} retry={retry} />,
    );

    fireEvent.press(getByLabelText('Retry loading CRAVE'));
    expect(retry).toHaveBeenCalledTimes(1);
  });
});
