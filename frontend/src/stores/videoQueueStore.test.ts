// Regression coverage for videoQueueStore.ts's offline record/sync flow --
// mirrors cravesStore.test.ts's mocking conventions.
jest.mock('@react-native-async-storage/async-storage', () => ({
  __esModule: true,
  default: {
    getItem: jest.fn(() => Promise.resolve(null)),
    setItem: jest.fn(() => Promise.resolve()),
    removeItem: jest.fn(() => Promise.resolve()),
  },
}));

jest.mock('expo-file-system/legacy', () => ({
  documentDirectory: 'file:///mock-docs/',
  makeDirectoryAsync: jest.fn(() => Promise.resolve()),
  moveAsync: jest.fn(() => Promise.resolve()),
  deleteAsync: jest.fn(() => Promise.resolve()),
  getInfoAsync: jest.fn(() => Promise.resolve({ exists: true })),
}));

jest.mock('../api/videos', () => ({
  requestVideoUpload: jest.fn(),
  confirmVideoUpload: jest.fn(),
  uploadVideoToSignedUrl: jest.fn(),
}));

async function flush(): Promise<void> {
  for (let i = 0; i < 15; i++) {
    await Promise.resolve();
  }
}

describe('videoQueueStore', () => {
  let useVideoQueueStore: typeof import('./videoQueueStore').useVideoQueueStore;
  let videosApi: typeof import('../api/videos');
  let FileSystem: typeof import('expo-file-system/legacy');

  beforeEach(() => {
    jest.resetModules();
    videosApi = require('../api/videos');
    (videosApi.requestVideoUpload as jest.Mock).mockReset();
    (videosApi.confirmVideoUpload as jest.Mock).mockReset();
    (videosApi.uploadVideoToSignedUrl as jest.Mock).mockReset();
    FileSystem = require('expo-file-system/legacy');
    (FileSystem.moveAsync as jest.Mock).mockClear();
    (FileSystem.deleteAsync as jest.Mock).mockClear();
    (FileSystem.getInfoAsync as jest.Mock).mockReset().mockResolvedValue({ exists: true });
    ({ useVideoQueueStore } = require('./videoQueueStore'));
  });

  it('records a video locally without touching the network', async () => {
    const video = await useVideoQueueStore.getState().recordVideo({
      sourceUri: 'file:///tmp/camera-output.mov',
      placeId: 'place-1',
      contentType: 'video/mp4',
      uploadedBy: 'user-a',
    });

    expect(video.syncState).toBe('recorded');
    expect(FileSystem.moveAsync).toHaveBeenCalledTimes(1);
    expect(videosApi.requestVideoUpload).not.toHaveBeenCalled();
    expect(useVideoQueueStore.getState().videos).toHaveLength(1);
  });

  it('refuses to queue past MAX_QUEUED_VIDEOS', async () => {
    for (let i = 0; i < 10; i++) {
      await useVideoQueueStore.getState().recordVideo({
        sourceUri: `file:///tmp/clip-${i}.mp4`,
        placeId: 'place-1',
        contentType: 'video/mp4',
        uploadedBy: 'user-a',
      });
    }

    await expect(
      useVideoQueueStore.getState().recordVideo({
        sourceUri: 'file:///tmp/one-too-many.mp4',
        placeId: 'place-1',
        contentType: 'video/mp4',
        uploadedBy: 'user-a',
      })
    ).rejects.toThrow(/waiting to post/);
  });

  it('syncs a recorded video through request -> upload -> confirm -> synced', async () => {
    (videosApi.requestVideoUpload as jest.Mock).mockResolvedValue({
      video_id: 'server-1',
      upload_url: 'https://r2.example.test/put',
      key: 'places/place-1/videos/orig/x.mp4',
    });
    (videosApi.uploadVideoToSignedUrl as jest.Mock).mockResolvedValue(undefined);
    (videosApi.confirmVideoUpload as jest.Mock).mockResolvedValue({ ok: true });

    await useVideoQueueStore.getState().recordVideo({
      sourceUri: 'file:///tmp/clip.mp4',
      placeId: 'place-1',
      contentType: 'video/mp4',
      uploadedBy: 'user-a',
    });

    await useVideoQueueStore.getState().runSyncPass('user-a');

    const [video] = useVideoQueueStore.getState().videos;
    expect(video.syncState).toBe('synced');
    expect(video.serverId).toBe('server-1');
    expect(videosApi.requestVideoUpload).toHaveBeenCalledWith(
      expect.objectContaining({ place_id: 'place-1', client_id: video.id })
    );
    expect(FileSystem.deleteAsync).toHaveBeenCalledWith(video.localUri, { idempotent: true });
  });

  it('does not sync a video recorded by a different (not currently signed-in) user', async () => {
    await useVideoQueueStore.getState().recordVideo({
      sourceUri: 'file:///tmp/clip.mp4',
      placeId: 'place-1',
      contentType: 'video/mp4',
      uploadedBy: 'user-b',
    });

    await useVideoQueueStore.getState().runSyncPass('user-a');

    expect(videosApi.requestVideoUpload).not.toHaveBeenCalled();
    expect(useVideoQueueStore.getState().videos[0].syncState).toBe('recorded');
  });

  it('records a failure and keeps the video retryable until MAX_ATTEMPTS', async () => {
    (videosApi.requestVideoUpload as jest.Mock).mockRejectedValue(new Error('Network Error'));

    await useVideoQueueStore.getState().recordVideo({
      sourceUri: 'file:///tmp/clip.mp4',
      placeId: 'place-1',
      contentType: 'video/mp4',
      uploadedBy: 'user-a',
    });

    await useVideoQueueStore.getState().runSyncPass('user-a');

    const [video] = useVideoQueueStore.getState().videos;
    expect(video.syncState).toBe('recorded'); // still under MAX_ATTEMPTS (5)
    expect(video.attemptCount).toBe(1);
    expect(video.lastError).toBe('Network Error');
  });

  it('moves a video to failed once MAX_ATTEMPTS is exhausted', async () => {
    (videosApi.requestVideoUpload as jest.Mock).mockRejectedValue(new Error('still broken'));

    await useVideoQueueStore.getState().recordVideo({
      sourceUri: 'file:///tmp/clip.mp4',
      placeId: 'place-1',
      contentType: 'video/mp4',
      uploadedBy: 'user-a',
    });

    for (let i = 0; i < 5; i++) {
      await useVideoQueueStore.getState().runSyncPass('user-a');
    }

    const [video] = useVideoQueueStore.getState().videos;
    expect(video.syncState).toBe('failed');
    expect(video.attemptCount).toBe(5);
  });

  it('retryFailedVideo resets a failed video back to recorded', async () => {
    (videosApi.requestVideoUpload as jest.Mock).mockRejectedValue(new Error('still broken'));
    await useVideoQueueStore.getState().recordVideo({
      sourceUri: 'file:///tmp/clip.mp4',
      placeId: 'place-1',
      contentType: 'video/mp4',
      uploadedBy: 'user-a',
    });
    for (let i = 0; i < 5; i++) {
      await useVideoQueueStore.getState().runSyncPass('user-a');
    }
    const failedId = useVideoQueueStore.getState().videos[0].id;

    useVideoQueueStore.getState().retryFailedVideo(failedId);

    const video = useVideoQueueStore.getState().videos[0];
    expect(video.syncState).toBe('recorded');
    expect(video.attemptCount).toBe(0);
    expect(video.lastError).toBeNull();
  });

  it('deleteFailedVideo removes the local file and the queue entry', async () => {
    (videosApi.requestVideoUpload as jest.Mock).mockRejectedValue(new Error('still broken'));
    await useVideoQueueStore.getState().recordVideo({
      sourceUri: 'file:///tmp/clip.mp4',
      placeId: 'place-1',
      contentType: 'video/mp4',
      uploadedBy: 'user-a',
    });
    for (let i = 0; i < 5; i++) {
      await useVideoQueueStore.getState().runSyncPass('user-a');
    }
    const video = useVideoQueueStore.getState().videos[0];

    await useVideoQueueStore.getState().deleteFailedVideo(video.id);

    expect(FileSystem.deleteAsync).toHaveBeenCalledWith(video.localUri, { idempotent: true });
    expect(useVideoQueueStore.getState().videos).toHaveLength(0);
  });

  it('drops the queue entry if the local file has been removed by the OS', async () => {
    (videosApi.requestVideoUpload as jest.Mock).mockResolvedValue({
      video_id: 'server-1',
      upload_url: 'https://r2.example.test/put',
      key: 'k',
    });
    (FileSystem.getInfoAsync as jest.Mock).mockResolvedValue({ exists: false });

    await useVideoQueueStore.getState().recordVideo({
      sourceUri: 'file:///tmp/clip.mp4',
      placeId: 'place-1',
      contentType: 'video/mp4',
      uploadedBy: 'user-a',
    });

    await useVideoQueueStore.getState().runSyncPass('user-a');

    expect(useVideoQueueStore.getState().videos).toHaveLength(0);
    expect(videosApi.uploadVideoToSignedUrl).not.toHaveBeenCalled();
  });
});
