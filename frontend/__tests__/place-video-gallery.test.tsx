// PlaceVideoGallery — first dedicated coverage.
//
// Found during an end-to-end wiring audit: this component had two real
// gaps. (1) "Record a video" was a toast-only dead end for a signed-out
// user (`toast('Sign in to record a food video'); return;`), the same
// class of bug already fixed everywhere else in the app this session --
// missed earlier only because the previous sweep grepped `frontend/app`
// (screens) and never looked at `frontend/src/components` (shared
// components rendered inside those screens). (2) videos had no report
// affordance at all, even though the backend's video-moderation pipeline
// (POST /moderation/videos/{id}/report, review queue, auto-hide) was
// fully built and already used identically for photos and places.
import React from 'react';
import { fireEvent, render, waitFor } from '@testing-library/react-native';
import { PlaceVideoGallery } from '../src/components/PlaceVideoGallery';
import { fetchVideoFeed } from '../src/api/videos';
import { useAuthStore } from '../src/stores/authStore';

const mockRouterPush = jest.fn();
jest.mock('expo-router', () => ({
  useRouter: () => ({ push: mockRouterPush }),
}));
jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  ImpactFeedbackStyle: { Light: 'light' },
  notificationAsync: jest.fn(),
  NotificationFeedbackType: { Success: 'success' },
}));
// A real VideoView can't render under RTL/jsdom -- stub it and the
// player hook the same way record-video.test.tsx stubs CameraView.
jest.mock('expo-video', () => ({
  useVideoPlayer: jest.fn(() => ({ loop: false, play: jest.fn() })),
  VideoView: () => null,
}));
jest.mock('../src/api/videos', () => ({
  fetchVideoFeed: jest.fn(),
}));
jest.mock('../src/stores/authStore', () => ({
  useAuthStore: jest.fn(),
}));
const mockRequestAuthGate = jest.fn();
jest.mock('../src/stores/authGateStore', () => ({
  requestAuthGate: (...args: unknown[]) => mockRequestAuthGate(...args),
}));
const mockToastShow = jest.fn();
jest.mock('../src/hooks/useToast', () => ({
  useToast: (selector: (s: { show: (msg: string) => void }) => unknown) =>
    selector({ show: mockToastShow }),
}));
jest.mock('../src/components/ReportVideoSheet', () => {
  const { Text } = require('react-native');
  return {
    ReportVideoSheet: ({ visible, videoId }: { visible: boolean; videoId: string | null }) =>
      visible ? <Text testID="report-video-sheet-visible">{videoId}</Text> : null,
  };
});

const mockedFetchVideoFeed = fetchVideoFeed as jest.MockedFunction<typeof fetchVideoFeed>;
const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;

function mockUser(user: { id: string } | null) {
  mockedUseAuthStore.mockImplementation((selector: (s: { user: unknown }) => unknown) =>
    selector({ user }),
  );
}

const oneVideo = {
  id: 'video-1',
  placeId: 'place-1',
  templateId: null,
  durationMs: 5000,
  thumbnailUrl: 'https://example.com/thumb.jpg',
  videoUrl: 'https://example.com/video.mp4',
};

describe('PlaceVideoGallery', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('gates "Record a video" through the shared auth gate for a signed-out user, instead of a dead-end toast', async () => {
    mockUser(null);
    mockedFetchVideoFeed.mockResolvedValue({ videos: [], limit: 20, offset: 0 });
    const { findByText } = render(<PlaceVideoGallery placeId="place-1" />);

    fireEvent.press(await findByText('Record a video'));

    expect(mockRequestAuthGate).toHaveBeenCalledWith(
      expect.objectContaining({
        actionType: 'record_place_video',
        reason: 'default',
        sourceRoute: '/place/place-1',
        targetIds: ['place-1'],
        destination: '/record-video/place-1',
        idempotent: true,
      }),
    );
    expect(mockRouterPush).not.toHaveBeenCalled();
  });

  it('navigates straight to record-video for a signed-in user', async () => {
    mockUser({ id: 'user-1' });
    mockedFetchVideoFeed.mockResolvedValue({ videos: [], limit: 20, offset: 0 });
    const { findByText } = render(<PlaceVideoGallery placeId="place-1" />);

    fireEvent.press(await findByText('Record a video'));

    expect(mockRouterPush).toHaveBeenCalledWith('/record-video/place-1');
    expect(mockRequestAuthGate).not.toHaveBeenCalled();
  });

  it('gates reporting a video through the shared auth gate for a signed-out user', async () => {
    mockUser(null);
    mockedFetchVideoFeed.mockResolvedValue({ videos: [oneVideo], limit: 20, offset: 0 });
    const { findByLabelText } = render(<PlaceVideoGallery placeId="place-1" />);

    fireEvent.press(await findByLabelText('Play video 1 of 1'));
    fireEvent.press(await findByLabelText('Report this video'));

    expect(mockRequestAuthGate).toHaveBeenCalledWith(
      expect.objectContaining({
        actionType: 'report_place_video',
        reason: 'default',
        sourceRoute: '/place/place-1',
        targetIds: ['video-1'],
      }),
    );
  });

  it('opens the report sheet directly for a signed-in user', async () => {
    mockUser({ id: 'user-1' });
    mockedFetchVideoFeed.mockResolvedValue({ videos: [oneVideo], limit: 20, offset: 0 });
    const { findByLabelText, findByTestId } = render(<PlaceVideoGallery placeId="place-1" />);

    fireEvent.press(await findByLabelText('Play video 1 of 1'));
    fireEvent.press(await findByLabelText('Report this video'));

    expect(await findByTestId('report-video-sheet-visible')).toBeTruthy();
    expect(mockRequestAuthGate).not.toHaveBeenCalled();
  });
});
