import React from 'react';
import { Alert, Switch } from 'react-native';
import { fireEvent, render, waitFor } from '@testing-library/react-native';

import OfflineUploadsScreen from '../app/offline-uploads';
import { useAuthStore } from '../src/stores/authStore';
import { useVideoQueueStore } from '../src/stores/videoQueueStore';
import type { QueuedVideo } from '../src/stores/videoQueueStore';

jest.mock('../src/stores/authStore', () => ({
  useAuthStore: jest.fn(),
}));

jest.mock('../src/stores/videoQueueStore', () => ({
  useVideoQueueStore: jest.fn(),
}));

jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  ImpactFeedbackStyle: { Light: 'light' },
}));

const mockToast = jest.fn();
jest.mock('../src/hooks/useToast', () => ({
  useToast: (selector: (s: { show: (msg: string) => void }) => unknown) =>
    selector({ show: mockToast }),
}));

const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;
const mockedUseVideoQueueStore = useVideoQueueStore as unknown as jest.Mock;
const mockRunSyncPass = jest.fn().mockResolvedValue(undefined);
const mockRetryFailedVideo = jest.fn();
const mockDeleteFailedVideo = jest.fn().mockResolvedValue(undefined);
const mockSetAutoSyncEnabled = jest.fn();

const baseStore: {
  videos: QueuedVideo[];
  autoSyncEnabled: boolean;
  setAutoSyncEnabled: typeof mockSetAutoSyncEnabled;
  runSyncPass: typeof mockRunSyncPass;
  retryFailedVideo: typeof mockRetryFailedVideo;
  deleteFailedVideo: typeof mockDeleteFailedVideo;
} = {
  videos: [],
  autoSyncEnabled: true,
  setAutoSyncEnabled: mockSetAutoSyncEnabled,
  runSyncPass: mockRunSyncPass,
  retryFailedVideo: mockRetryFailedVideo,
  deleteFailedVideo: mockDeleteFailedVideo,
};

function mockVideoStore(overrides: Partial<typeof baseStore>) {
  mockedUseVideoQueueStore.mockImplementation((selector: (s: unknown) => unknown) =>
    selector({ ...baseStore, ...overrides }),
  );
}

describe('OfflineUploadsScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedUseAuthStore.mockImplementation((selector: (s: unknown) => unknown) =>
      selector({ user: { id: 'user-1', email: 'a@b.com' } }),
    );
    mockVideoStore({});
    jest.spyOn(Alert, 'alert').mockImplementation(() => {});
  });

  it('shows an empty caught-up state for a signed-in user with no queued uploads', () => {
    const { getByText } = render(<OfflineUploadsScreen />);

    expect(getByText('All caught up')).toBeTruthy();
    expect(getByText('No food videos are waiting on this phone.')).toBeTruthy();
  });

  it('forces a manual sync even when auto-sync is disabled', async () => {
    mockVideoStore({ autoSyncEnabled: false });
    const { getByLabelText } = render(<OfflineUploadsScreen />);

    fireEvent.press(getByLabelText('Sync queued uploads now'));

    await waitFor(() => {
      expect(mockRunSyncPass).toHaveBeenCalledWith('user-1', { force: true });
    });
  });

  it('lets the user toggle automatic sync', () => {
    const { UNSAFE_getByType } = render(<OfflineUploadsScreen />);

    fireEvent(UNSAFE_getByType(Switch), 'valueChange', false);

    expect(mockSetAutoSyncEnabled).toHaveBeenCalledWith(false);
  });

  it('retries a failed clip and immediately runs a forced sync', async () => {
    mockVideoStore({
      videos: [
        {
          id: 'video-1',
          uploadedBy: 'user-1',
          localUri: 'file:///clip.mp4',
          placeId: 'place-1',
          templateId: null,
          contentType: 'video/mp4',
          syncState: 'failed',
          attemptCount: 5,
          lastAttemptAt: Date.now(),
          lastError: 'Network Error',
          progressPct: null,
          createdAt: Date.now(),
          serverId: null,
        },
      ],
    });

    const { getByLabelText, getByText } = render(<OfflineUploadsScreen />);
    expect(getByText('Needs retry')).toBeTruthy();

    fireEvent.press(getByLabelText('Retry upload'));

    expect(mockRetryFailedVideo).toHaveBeenCalledWith('video-1');
    await waitFor(() => {
      expect(mockRunSyncPass).toHaveBeenCalledWith('user-1', { force: true });
    });
  });

  it('confirms before deleting a failed local clip', () => {
    mockVideoStore({
      videos: [
        {
          id: 'video-1',
          uploadedBy: 'user-1',
          localUri: 'file:///clip.mp4',
          placeId: 'place-1',
          templateId: null,
          contentType: 'video/mp4',
          syncState: 'failed',
          attemptCount: 5,
          lastAttemptAt: Date.now(),
          lastError: 'Network Error',
          progressPct: null,
          createdAt: Date.now(),
          serverId: null,
        },
      ],
    });

    const { getByLabelText } = render(<OfflineUploadsScreen />);
    fireEvent.press(getByLabelText('Remove upload from queue'));

    expect(Alert.alert).toHaveBeenCalledWith(
      'Delete this saved clip?',
      expect.stringContaining('removes the local video file'),
      expect.any(Array),
    );

    const buttons = (Alert.alert as jest.Mock).mock.calls[0][2] as Array<{ text: string; onPress?: () => void }>;
    buttons.find((button) => button.text === 'Delete')?.onPress?.();
    expect(mockDeleteFailedVideo).toHaveBeenCalledWith('video-1');
  });

  it('does not expose another account’s queued clips to the signed-in user', () => {
    mockVideoStore({
      videos: [
        {
          id: 'video-2',
          uploadedBy: 'user-2',
          localUri: 'file:///clip.mp4',
          placeId: 'place-1',
          templateId: null,
          contentType: 'video/mp4',
          syncState: 'failed',
          attemptCount: 5,
          lastAttemptAt: Date.now(),
          lastError: 'Network Error',
          progressPct: null,
          createdAt: Date.now(),
          serverId: null,
        },
      ],
    });

    const { getByText, queryByText } = render(<OfflineUploadsScreen />);

    expect(getByText('All caught up')).toBeTruthy();
    expect(queryByText('Needs retry')).toBeNull();
  });

  it('does not expose queued clip counts or rows while signed out', () => {
    mockedUseAuthStore.mockImplementation((selector: (s: unknown) => unknown) =>
      selector({ user: null }),
    );
    mockVideoStore({
      videos: [
        {
          id: 'video-2',
          uploadedBy: 'user-2',
          localUri: 'file:///clip.mp4',
          placeId: 'place-1',
          templateId: null,
          contentType: 'video/mp4',
          syncState: 'failed',
          attemptCount: 5,
          lastAttemptAt: Date.now(),
          lastError: 'Network Error',
          progressPct: null,
          createdAt: Date.now(),
          serverId: null,
        },
      ],
    });

    const { getByText, queryByText } = render(<OfflineUploadsScreen />);

    expect(getByText('Sign in to manage uploads')).toBeTruthy();
    expect(getByText('No queued video uploads.')).toBeTruthy();
    expect(queryByText('Needs retry')).toBeNull();
  });
});
