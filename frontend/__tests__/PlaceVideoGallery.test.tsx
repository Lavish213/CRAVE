// PlaceVideoGallery -- first dedicated coverage. Locks in the new
// local-queue merge: a video this device has recorded/queued/is
// uploading/is under review for this exact place shows up as a
// placeholder tile right alongside the server-approved feed, instead of
// being invisible until the backend's moderation worker approves it.
import React from 'react';
import { render, fireEvent, waitFor, act } from '@testing-library/react-native';
import { PlaceVideoGallery } from '../src/components/PlaceVideoGallery';
import { useAuthStore } from '../src/stores/authStore';
import { useVideoQueueStore, QueuedVideo } from '../src/stores/videoQueueStore';
import { fetchVideoFeed, FeedVideo } from '../src/api/videos';

const mockPush = jest.fn();
jest.mock('expo-router', () => ({
  useRouter: () => ({ push: mockPush }),
}));

jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  ImpactFeedbackStyle: { Light: 'light' },
}));

jest.mock('expo-image', () => ({ Image: () => null }));
const mockUseVideoPlayer = jest.fn((_source: string, _config?: (player: unknown) => void) => ({
  loop: false,
  play: jest.fn(),
}));
jest.mock('expo-video', () => ({
  useVideoPlayer: (source: string, config?: (player: unknown) => void) => mockUseVideoPlayer(source, config),
  VideoView: () => null,
}));
jest.mock('../src/components/ReportVideoSheet', () => ({ ReportVideoSheet: () => null }));
jest.mock('../src/stores/authGateStore', () => ({ requestAuthGate: jest.fn() }));

let mockUser: { id: string } | null = { id: 'user-1' };
jest.mock('../src/stores/authStore', () => ({
  useAuthStore: (selector: (s: { user: typeof mockUser }) => unknown) => selector({ user: mockUser }),
}));

// videoQueueStore.ts itself imports requestVideoUpload/confirmVideoUpload/
// uploadVideoToSignedUrl from this same module -- stubbed here (mirrors
// uploads.test.tsx's own convention) so the store still imports cleanly,
// even though these tests never exercise the real sync path.
jest.mock('../src/api/videos', () => ({
  fetchVideoFeed: jest.fn(),
  requestVideoUpload: jest.fn(),
  confirmVideoUpload: jest.fn(),
  uploadVideoToSignedUrl: jest.fn(),
}));
const mockedFetchVideoFeed = fetchVideoFeed as jest.MockedFunction<typeof fetchVideoFeed>;

function makeVideo(overrides: Partial<QueuedVideo>): QueuedVideo {
  return {
    id: 'v1', serverId: null, localUri: 'file:///v1.mp4', placeId: 'place-1', templateId: null,
    contentType: 'video/mp4', uploadedBy: 'user-1', syncState: 'recorded', attemptCount: 0,
    lastAttemptAt: null, lastError: null, createdAt: Date.now(), ...overrides,
  };
}

function makeFeedVideo(overrides: Partial<FeedVideo>): FeedVideo {
  return {
    id: 'server-v1', placeId: 'place-1', templateId: null, durationMs: 5000,
    thumbnailUrl: 'https://cdn.example/thumb.jpg', videoUrl: 'https://cdn.example/v.mp4', ...overrides,
  };
}

describe('PlaceVideoGallery', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUser = { id: 'user-1' };
    useVideoQueueStore.setState({ videos: [] });
    mockedFetchVideoFeed.mockResolvedValue({ videos: [], limit: 20, offset: 0 });
  });

  it('shows only the Record chip when there is nothing local or server-side for this place', async () => {
    const { getByText, queryByText } = render(<PlaceVideoGallery placeId="place-1" />);
    await waitFor(() => expect(mockedFetchVideoFeed).toHaveBeenCalled());
    expect(getByText('Record a video')).toBeTruthy();
    expect(queryByText('Queued')).toBeNull();
  });

  it('shows a locally queued video for this place as a placeholder tile', async () => {
    useVideoQueueStore.setState({ videos: [makeVideo({ syncState: 'recorded' })] });
    const { getByText, getByLabelText } = render(<PlaceVideoGallery placeId="place-1" />);
    await waitFor(() => expect(mockedFetchVideoFeed).toHaveBeenCalled());
    expect(getByText('Queued')).toBeTruthy();
    expect(getByLabelText('Queued — view in your uploads')).toBeTruthy();
  });

  it('shows the right copy for each in-progress sync state', async () => {
    useVideoQueueStore.setState({
      videos: [
        makeVideo({ id: 'a', syncState: 'uploading' }),
        makeVideo({ id: 'b', placeId: 'place-2', syncState: 'reviewing' }),
      ],
    });
    const { getByText, queryByText } = render(<PlaceVideoGallery placeId="place-1" />);
    await waitFor(() => expect(mockedFetchVideoFeed).toHaveBeenCalled());
    expect(getByText('Uploading…')).toBeTruthy();
    // Belongs to a different place -- must not leak into this gallery.
    expect(queryByText('Under review')).toBeNull();
  });

  it('excludes another user\'s queued video, and this user\'s terminal-state videos', async () => {
    useVideoQueueStore.setState({
      videos: [
        makeVideo({ id: 'other-user', uploadedBy: 'someone-else', syncState: 'recorded' }),
        makeVideo({ id: 'failed', syncState: 'failed' }),
        makeVideo({ id: 'rejected', syncState: 'rejected' }),
        makeVideo({ id: 'synced', syncState: 'synced' }),
        makeVideo({ id: 'missing', syncState: 'missing_local_file' }),
      ],
    });
    const { getByText, queryByText } = render(<PlaceVideoGallery placeId="place-1" />);
    await waitFor(() => expect(mockedFetchVideoFeed).toHaveBeenCalled());
    expect(getByText('Record a video')).toBeTruthy();
    expect(queryByText('Queued')).toBeNull();
    expect(queryByText('Uploading…')).toBeNull();
    expect(queryByText('Under review')).toBeNull();
  });

  it('places the local placeholder ahead of the server-approved feed', async () => {
    mockedFetchVideoFeed.mockResolvedValue({
      videos: [makeFeedVideo({})],
      limit: 20,
      offset: 0,
    });
    useVideoQueueStore.setState({ videos: [makeVideo({ syncState: 'reviewing' })] });
    const { getByText, getByLabelText } = render(<PlaceVideoGallery placeId="place-1" />);
    await waitFor(() => expect(getByLabelText('Play video 1 of 1')).toBeTruthy());
    expect(getByText('Under review')).toBeTruthy();
  });

  it('navigates to the Uploads screen when a placeholder is pressed', async () => {
    useVideoQueueStore.setState({ videos: [makeVideo({ syncState: 'uploading' })] });
    const { getByLabelText } = render(<PlaceVideoGallery placeId="place-1" />);
    await waitFor(() => expect(mockedFetchVideoFeed).toHaveBeenCalled());
    fireEvent.press(getByLabelText('Uploading… — view in your uploads'));
    expect(mockPush).toHaveBeenCalledWith('/uploads');
  });

  it('refetches the server feed once a locally queued video for this place resolves away (e.g. approved and pruned)', async () => {
    useVideoQueueStore.setState({ videos: [makeVideo({ id: 'v1', syncState: 'reviewing' })] });
    const { getByText } = render(<PlaceVideoGallery placeId="place-1" />);
    await waitFor(() => expect(mockedFetchVideoFeed).toHaveBeenCalledTimes(1));
    expect(getByText('Under review')).toBeTruthy();

    mockedFetchVideoFeed.mockResolvedValue({
      videos: [makeFeedVideo({ id: 'v1' })],
      limit: 20,
      offset: 0,
    });
    // Mirrors what videoQueueStore's own prune-on-next-pass logic does once
    // applyVideoReviewResult resolves 'reviewing' to 'synced' and a later
    // sync pass prunes it -- the row simply disappears from this store.
    act(() => {
      useVideoQueueStore.setState({ videos: [] });
    });

    await waitFor(() => expect(mockedFetchVideoFeed).toHaveBeenCalledTimes(2));
  });

  it('ignores a stale response from an earlier request that resolves after a newer one', async () => {
    // Confirmed CodeRabbit finding on PR #314: the initial-mount fetch and
    // the placeholder-loss refetch both called setVideos unconditionally --
    // if the initial (older) request happened to resolve *after* a newer
    // refetch had already applied its own result, the stale response would
    // silently win and overwrite the newer data.
    let resolveFirst: ((v: { videos: FeedVideo[]; limit: number; offset: number }) => void) | undefined;
    let resolveSecond: ((v: { videos: FeedVideo[]; limit: number; offset: number }) => void) | undefined;
    mockedFetchVideoFeed
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveFirst = resolve;
        })
      )
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveSecond = resolve;
        })
      );

    useVideoQueueStore.setState({ videos: [makeVideo({ id: 'v1', syncState: 'reviewing' })] });
    const { getByLabelText } = render(<PlaceVideoGallery placeId="place-1" />);
    await waitFor(() => expect(mockedFetchVideoFeed).toHaveBeenCalledTimes(1));

    // Triggers the second (newer) fetch via the placeholder-loss path while
    // the first (mount) fetch is still unresolved.
    await act(async () => {
      useVideoQueueStore.setState({ videos: [] });
    });
    await waitFor(() => expect(mockedFetchVideoFeed).toHaveBeenCalledTimes(2));

    // The newer request resolves first -- `act`'s async form awaits its own
    // callback, which here includes the promise's `.then` continuation
    // (via the extra microtask flush below), so the resulting setVideos
    // call is committed to the render tree before the next line runs.
    await act(async () => {
      resolveSecond?.({
        videos: [makeFeedVideo({ id: 'newer', videoUrl: 'https://cdn.example/newer.mp4' })],
        limit: 20,
        offset: 0,
      });
      await Promise.resolve();
    });

    // ...then the older request finally resolves with different data.
    await act(async () => {
      resolveFirst?.({
        videos: [makeFeedVideo({ id: 'stale', videoUrl: 'https://cdn.example/stale.mp4' })],
        limit: 20,
        offset: 0,
      });
      await Promise.resolve();
    });

    fireEvent.press(getByLabelText('Play video 1 of 1'));
    expect(mockUseVideoPlayer).toHaveBeenCalledWith('https://cdn.example/newer.mp4', expect.any(Function));
    expect(mockUseVideoPlayer).not.toHaveBeenCalledWith('https://cdn.example/stale.mp4', expect.any(Function));
  });

  it('does not refetch on the initial mount just because there were no placeholders to begin with', async () => {
    render(<PlaceVideoGallery placeId="place-1" />);
    await waitFor(() => expect(mockedFetchVideoFeed).toHaveBeenCalledTimes(1));
    // No further calls should follow from the placeholder-tracking effect
    // simply observing an empty set on mount.
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(mockedFetchVideoFeed).toHaveBeenCalledTimes(1);
  });
});
