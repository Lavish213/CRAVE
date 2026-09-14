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

jest.mock('@react-native-community/netinfo', () => ({
  __esModule: true,
  default: {
    fetch: jest.fn(() =>
      Promise.resolve({ type: 'wifi', isConnected: true, isInternetReachable: true, details: {} })
    ),
    addEventListener: jest.fn(() => jest.fn()),
  },
}));

async function flush(): Promise<void> {
  for (let i = 0; i < 15; i++) {
    await Promise.resolve();
  }
}

// Controls Date.now() for the exponential-backoff tests without touching
// real timers -- the store never uses setTimeout/setInterval itself (each
// retry is externally triggered by the test calling runSyncPass again), so
// mocking Date.now() directly is simpler and safer than fake timers here,
// which would risk interfering with the store's own async/await chains.
function mockClock(startMs = 1_700_000_000_000) {
  let now = startMs;
  const spy = jest.spyOn(Date, 'now').mockImplementation(() => now);
  return {
    advance: (ms: number) => {
      now += ms;
    },
    restore: () => spy.mockRestore(),
  };
}

// Longer than the backoff cap (5 minutes) -- guarantees the next
// runSyncPass call is never skipped for still being within a backoff
// window, regardless of how high attemptCount has climbed.
const PAST_MAX_BACKOFF_MS = 6 * 60_000;

describe('videoQueueStore', () => {
  let useVideoQueueStore: typeof import('./videoQueueStore').useVideoQueueStore;
  let videosApi: typeof import('../api/videos');
  let FileSystem: typeof import('expo-file-system/legacy');
  let NetInfo: typeof import('@react-native-community/netinfo').default;
  let useUploadPreferencesStore: typeof import('./uploadPreferencesStore').useUploadPreferencesStore;

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
    NetInfo = require('@react-native-community/netinfo').default;
    (NetInfo.fetch as jest.Mock)
      .mockReset()
      .mockResolvedValue({ type: 'wifi', isConnected: true, isInternetReachable: true, details: {} });
    ({ useUploadPreferencesStore } = require('./uploadPreferencesStore'));
    useUploadPreferencesStore.setState({ wifiOnlyVideoUploads: false });
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

  it('syncs a recorded video through request -> upload -> confirm -> reviewing', async () => {
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

    // 'reviewing', not 'synced' -- the upload itself succeeded, but the
    // backend's moderation review hasn't resolved yet (see
    // applyVideoReviewResult, driven by useVideoStatusPoll).
    const [video] = useVideoQueueStore.getState().videos;
    expect(video.syncState).toBe('reviewing');
    expect(video.serverId).toBe('server-1');
    expect(videosApi.requestVideoUpload).toHaveBeenCalledWith(
      expect.objectContaining({ place_id: 'place-1', client_id: video.id })
    );
    // The local file is freed immediately on a successful upload,
    // regardless of the review outcome still being unknown.
    expect(FileSystem.deleteAsync).toHaveBeenCalledWith(video.localUri, { idempotent: true });
  });

  describe('applyVideoReviewResult', () => {
    async function syncOneReviewingVideo() {
      (videosApi.requestVideoUpload as jest.Mock).mockResolvedValue({
        video_id: 'server-1', upload_url: 'https://r2.example.test/put', key: 'k',
      });
      (videosApi.uploadVideoToSignedUrl as jest.Mock).mockResolvedValue(undefined);
      (videosApi.confirmVideoUpload as jest.Mock).mockResolvedValue({ ok: true });

      const video = await useVideoQueueStore.getState().recordVideo({
        sourceUri: 'file:///tmp/clip.mp4', placeId: 'place-1', contentType: 'video/mp4', uploadedBy: 'user-a',
      });
      await useVideoQueueStore.getState().runSyncPass('user-a');
      expect(useVideoQueueStore.getState().videos[0].syncState).toBe('reviewing');
      return video;
    }

    it('resolves an approved video to synced', async () => {
      const video = await syncOneReviewingVideo();
      useVideoQueueStore.getState().applyVideoReviewResult(video.id, 'approved', null);
      expect(useVideoQueueStore.getState().videos[0].syncState).toBe('synced');
    });

    it('resolves a rejected video to rejected, with the reject reason surfaced', async () => {
      const video = await syncOneReviewingVideo();
      useVideoQueueStore.getState().applyVideoReviewResult(video.id, 'rejected', 'No food visible');
      const updated = useVideoQueueStore.getState().videos[0];
      expect(updated.syncState).toBe('rejected');
      expect(updated.lastError).toBe('No food visible');
    });

    it('leaves a still-processing video alone', async () => {
      const video = await syncOneReviewingVideo();
      useVideoQueueStore.getState().applyVideoReviewResult(video.id, 'processing', null);
      expect(useVideoQueueStore.getState().videos[0].syncState).toBe('reviewing');
    });

    it('ignores a review result for a video that is not (or no longer) reviewing', async () => {
      const video = await syncOneReviewingVideo();
      useVideoQueueStore.getState().applyVideoReviewResult(video.id, 'approved', null);
      // Already resolved to 'synced' -- a stale/duplicate poll callback
      // must not re-process it (e.g. flip an already-'rejected' video
      // back based on a late in-flight request).
      useVideoQueueStore.getState().applyVideoReviewResult(video.id, 'rejected', 'late callback');
      expect(useVideoQueueStore.getState().videos[0].syncState).toBe('synced');
    });
  });

  it('prunes a previously approved (now synced) video at the start of the next sync pass, not the same call that resolved it', async () => {
    // Confirmed gap: syncOne marks a video 'synced' and deletes its local
    // file, but nothing ever removed the row itself from the persisted
    // `videos` array -- unbounded growth, since nothing reads 'synced'
    // entries back out. Pruning must happen on a *later* pass, not
    // immediately, so a caller that just resolved a video to 'synced'
    // (like the tests above) still sees it.
    (videosApi.requestVideoUpload as jest.Mock).mockResolvedValue({
      video_id: 'server-1',
      upload_url: 'https://r2.example.test/put',
      key: 'k',
    });
    (videosApi.uploadVideoToSignedUrl as jest.Mock).mockResolvedValue(undefined);
    (videosApi.confirmVideoUpload as jest.Mock).mockResolvedValue({ ok: true });

    const video = await useVideoQueueStore.getState().recordVideo({
      sourceUri: 'file:///tmp/clip.mp4',
      placeId: 'place-1',
      contentType: 'video/mp4',
      uploadedBy: 'user-a',
    });

    await useVideoQueueStore.getState().runSyncPass('user-a');
    useVideoQueueStore.getState().applyVideoReviewResult(video.id, 'approved', null);
    expect(useVideoQueueStore.getState().videos).toHaveLength(1);
    expect(useVideoQueueStore.getState().videos[0].syncState).toBe('synced');

    // A later pass (e.g. the next foreground event) with nothing new to
    // sync must still clear the stale synced row.
    await useVideoQueueStore.getState().runSyncPass('user-a');
    expect(useVideoQueueStore.getState().videos).toHaveLength(0);
  });

  it('does not prune a synced video whose local file deletion still fails on the retry, so its localUri is never lost', async () => {
    // Confirmed CodeRabbit finding on PR #307: syncOne's own deleteAsync
    // call swallows a real (non-"already gone") failure and still marks
    // the video 'reviewing' (now resolved to 'synced' once approved) --
    // the prune step must not then blindly drop that row too, or the
    // file is orphaned on disk forever with no remaining reference to it.
    (videosApi.requestVideoUpload as jest.Mock).mockResolvedValue({
      video_id: 'server-1', upload_url: 'https://r2.example.test/put', key: 'k',
    });
    (videosApi.uploadVideoToSignedUrl as jest.Mock).mockResolvedValue(undefined);
    (videosApi.confirmVideoUpload as jest.Mock).mockResolvedValue({ ok: true });

    const recorded = await useVideoQueueStore.getState().recordVideo({
      sourceUri: 'file:///tmp/clip.mp4', placeId: 'place-1', contentType: 'video/mp4', uploadedBy: 'user-a',
    });
    await useVideoQueueStore.getState().runSyncPass('user-a');
    useVideoQueueStore.getState().applyVideoReviewResult(recorded.id, 'approved', null);
    const synced = useVideoQueueStore.getState().videos[0];
    expect(synced.syncState).toBe('synced');

    // Every subsequent deleteAsync call (syncOne's own, already spent
    // above, plus every prune retry) genuinely fails -- simulating a
    // real, persistent local-filesystem error, not "already gone".
    (FileSystem.deleteAsync as jest.Mock).mockRejectedValue(new Error('EACCES'));

    await useVideoQueueStore.getState().runSyncPass('user-a');
    const stillThere = useVideoQueueStore.getState().videos.find((v) => v.id === synced.id);
    expect(stillThere).toBeDefined();
    expect(stillThere?.syncState).toBe('synced');
    expect(stillThere?.localUri).toBe(synced.localUri);
  });

  it('prunes a synced video once a later retry of its file deletion finally succeeds', async () => {
    (videosApi.requestVideoUpload as jest.Mock).mockResolvedValue({
      video_id: 'server-1', upload_url: 'https://r2.example.test/put', key: 'k',
    });
    (videosApi.uploadVideoToSignedUrl as jest.Mock).mockResolvedValue(undefined);
    (videosApi.confirmVideoUpload as jest.Mock).mockResolvedValue({ ok: true });

    const recorded = await useVideoQueueStore.getState().recordVideo({
      sourceUri: 'file:///tmp/clip.mp4', placeId: 'place-1', contentType: 'video/mp4', uploadedBy: 'user-a',
    });
    await useVideoQueueStore.getState().runSyncPass('user-a');
    useVideoQueueStore.getState().applyVideoReviewResult(recorded.id, 'approved', null);

    // First prune retry fails (transient), second succeeds.
    (FileSystem.deleteAsync as jest.Mock).mockRejectedValueOnce(new Error('EACCES'));
    await useVideoQueueStore.getState().runSyncPass('user-a');
    expect(useVideoQueueStore.getState().videos).toHaveLength(1);

    await useVideoQueueStore.getState().runSyncPass('user-a');
    expect(useVideoQueueStore.getState().videos).toHaveLength(0);
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

  describe('Wi-Fi-only video uploads', () => {
    it('ignores connectivity entirely when the preference is off (default) -- never even checks', async () => {
      (videosApi.requestVideoUpload as jest.Mock).mockResolvedValue({
        video_id: 'server-1', upload_url: 'https://r2.example.test/put', key: 'k',
      });
      (videosApi.uploadVideoToSignedUrl as jest.Mock).mockResolvedValue(undefined);
      (videosApi.confirmVideoUpload as jest.Mock).mockResolvedValue({ ok: true });
      (NetInfo.fetch as jest.Mock).mockResolvedValue({
        type: 'cellular', isConnected: true, isInternetReachable: true, details: {},
      });

      await useVideoQueueStore.getState().recordVideo({
        sourceUri: 'file:///tmp/clip.mp4', placeId: 'place-1', contentType: 'video/mp4', uploadedBy: 'user-a',
      });
      await useVideoQueueStore.getState().runSyncPass('user-a');

      expect(NetInfo.fetch).not.toHaveBeenCalled();
      expect(videosApi.requestVideoUpload).toHaveBeenCalled();
      expect(useVideoQueueStore.getState().videos[0].syncState).toBe('reviewing');
    });

    it('holds a queued video untouched on a cellular connection when the preference is on', async () => {
      useUploadPreferencesStore.getState().setWifiOnlyVideoUploads(true);
      (NetInfo.fetch as jest.Mock).mockResolvedValue({
        type: 'cellular', isConnected: true, isInternetReachable: true, details: {},
      });

      await useVideoQueueStore.getState().recordVideo({
        sourceUri: 'file:///tmp/clip.mp4', placeId: 'place-1', contentType: 'video/mp4', uploadedBy: 'user-a',
      });
      await useVideoQueueStore.getState().runSyncPass('user-a');

      expect(videosApi.requestVideoUpload).not.toHaveBeenCalled();
      expect(useVideoQueueStore.getState().videos[0].syncState).toBe('recorded');
    });

    it('proceeds on a Wi-Fi connection when the preference is on', async () => {
      useUploadPreferencesStore.getState().setWifiOnlyVideoUploads(true);
      (videosApi.requestVideoUpload as jest.Mock).mockResolvedValue({
        video_id: 'server-1', upload_url: 'https://r2.example.test/put', key: 'k',
      });
      (videosApi.uploadVideoToSignedUrl as jest.Mock).mockResolvedValue(undefined);
      (videosApi.confirmVideoUpload as jest.Mock).mockResolvedValue({ ok: true });
      (NetInfo.fetch as jest.Mock).mockResolvedValue({
        type: 'wifi', isConnected: true, isInternetReachable: true, details: {},
      });

      await useVideoQueueStore.getState().recordVideo({
        sourceUri: 'file:///tmp/clip.mp4', placeId: 'place-1', contentType: 'video/mp4', uploadedBy: 'user-a',
      });
      await useVideoQueueStore.getState().runSyncPass('user-a');

      expect(videosApi.requestVideoUpload).toHaveBeenCalled();
      expect(useVideoQueueStore.getState().videos[0].syncState).toBe('reviewing');
    });

    it('treats ethernet the same as Wi-Fi (not metered)', async () => {
      useUploadPreferencesStore.getState().setWifiOnlyVideoUploads(true);
      (videosApi.requestVideoUpload as jest.Mock).mockResolvedValue({
        video_id: 'server-1', upload_url: 'https://r2.example.test/put', key: 'k',
      });
      (videosApi.uploadVideoToSignedUrl as jest.Mock).mockResolvedValue(undefined);
      (videosApi.confirmVideoUpload as jest.Mock).mockResolvedValue({ ok: true });
      (NetInfo.fetch as jest.Mock).mockResolvedValue({
        type: 'ethernet', isConnected: true, isInternetReachable: true, details: {},
      });

      await useVideoQueueStore.getState().recordVideo({
        sourceUri: 'file:///tmp/clip.mp4', placeId: 'place-1', contentType: 'video/mp4', uploadedBy: 'user-a',
      });
      await useVideoQueueStore.getState().runSyncPass('user-a');

      expect(videosApi.requestVideoUpload).toHaveBeenCalled();
    });
  });

  describe('reconnect while a pass is already in flight', () => {
    it('drains a request that arrived mid-pass instead of silently dropping it once the active pass clears', async () => {
      // Confirmed CodeRabbit finding on PR #312: connectivity returning
      // while a pass is already running used to just no-op (the
      // syncInFlight guard). If the in-flight upload then failed, nothing
      // was left to retry it beyond whatever unrelated event happened to
      // fire next.
      (videosApi.requestVideoUpload as jest.Mock).mockResolvedValue({
        video_id: 'server-1', upload_url: 'https://r2.example.test/put', key: 'k',
      });
      let rejectUpload: ((err: Error) => void) | undefined;
      (videosApi.uploadVideoToSignedUrl as jest.Mock).mockImplementation(
        () => new Promise<void>((_resolve, reject) => { rejectUpload = reject; })
      );

      await useVideoQueueStore.getState().recordVideo({
        sourceUri: 'file:///tmp/clip.mp4', placeId: 'place-1', contentType: 'video/mp4', uploadedBy: 'user-a',
      });

      const runSyncPassSpy = jest.spyOn(useVideoQueueStore.getState(), 'runSyncPass');

      const firstPass = useVideoQueueStore.getState().runSyncPass('user-a');
      await flush();
      expect(videosApi.uploadVideoToSignedUrl).toHaveBeenCalledTimes(1);

      // Simulates the NetInfo listener firing mid-upload (a brief drop and
      // reconnect) -- must be a no-op right now, not a second concurrent
      // syncOne for the same video.
      await useVideoQueueStore.getState().runSyncPass('user-a');
      expect(videosApi.requestVideoUpload).toHaveBeenCalledTimes(1);

      rejectUpload?.(new Error('Network Error'));
      await firstPass;
      await flush();

      // The drained call is a real extra pass (3rd), not just the two
      // explicit calls above -- without the fix there would be no 3rd.
      expect(runSyncPassSpy).toHaveBeenCalledTimes(3);
      // The just-failed video's own backoff still applies -- the drained
      // pass must not retry it immediately just because it ran.
      expect(videosApi.requestVideoUpload).toHaveBeenCalledTimes(1);
      expect(useVideoQueueStore.getState().videos[0].attemptCount).toBe(1);
    });
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
    expect(video.lastAttemptAt).not.toBeNull();
    expect(video.lastError).toBe('Network Error');
  });

  describe('exponential backoff', () => {
    it('does not retry a video still within its backoff window', async () => {
      (videosApi.requestVideoUpload as jest.Mock).mockRejectedValue(new Error('Network Error'));
      const clock = mockClock();

      try {
        await useVideoQueueStore.getState().recordVideo({
          sourceUri: 'file:///tmp/clip.mp4',
          placeId: 'place-1',
          contentType: 'video/mp4',
          uploadedBy: 'user-a',
        });

        await useVideoQueueStore.getState().runSyncPass('user-a'); // attempt 1 -> 5s backoff
        (videosApi.requestVideoUpload as jest.Mock).mockClear();

        clock.advance(1_000); // well under the 5s backoff window
        await useVideoQueueStore.getState().runSyncPass('user-a');

        expect(videosApi.requestVideoUpload).not.toHaveBeenCalled();
        expect(useVideoQueueStore.getState().videos[0].attemptCount).toBe(1);
      } finally {
        clock.restore();
      }
    });

    it('retries a video once its backoff window has elapsed', async () => {
      (videosApi.requestVideoUpload as jest.Mock).mockRejectedValue(new Error('Network Error'));
      const clock = mockClock();

      try {
        await useVideoQueueStore.getState().recordVideo({
          sourceUri: 'file:///tmp/clip.mp4',
          placeId: 'place-1',
          contentType: 'video/mp4',
          uploadedBy: 'user-a',
        });

        await useVideoQueueStore.getState().runSyncPass('user-a'); // attempt 1 -> 5s backoff
        (videosApi.requestVideoUpload as jest.Mock).mockClear();

        clock.advance(10_000); // past the 5s backoff window
        await useVideoQueueStore.getState().runSyncPass('user-a');

        expect(videosApi.requestVideoUpload).toHaveBeenCalledTimes(1);
        expect(useVideoQueueStore.getState().videos[0].attemptCount).toBe(2);
      } finally {
        clock.restore();
      }
    });

    it('retryFailedVideo makes a video immediately retryable again, ignoring backoff', async () => {
      (videosApi.requestVideoUpload as jest.Mock).mockRejectedValue(new Error('still broken'));
      const clock = mockClock();

      try {
        await useVideoQueueStore.getState().recordVideo({
          sourceUri: 'file:///tmp/clip.mp4',
          placeId: 'place-1',
          contentType: 'video/mp4',
          uploadedBy: 'user-a',
        });
        for (let i = 0; i < 5; i++) {
          await useVideoQueueStore.getState().runSyncPass('user-a');
          clock.advance(PAST_MAX_BACKOFF_MS);
        }
        const failedId = useVideoQueueStore.getState().videos[0].id;
        useVideoQueueStore.getState().retryFailedVideo(failedId);

        (videosApi.requestVideoUpload as jest.Mock).mockClear();
        (videosApi.requestVideoUpload as jest.Mock).mockRejectedValue(new Error('still broken'));
        // No clock advance here -- retryFailedVideo must reset lastAttemptAt
        // so the very next sync pass is not gated by the old backoff state.
        await useVideoQueueStore.getState().runSyncPass('user-a');

        expect(videosApi.requestVideoUpload).toHaveBeenCalledTimes(1);
      } finally {
        clock.restore();
      }
    });
  });

  it('moves a video to failed once MAX_ATTEMPTS is exhausted', async () => {
    (videosApi.requestVideoUpload as jest.Mock).mockRejectedValue(new Error('still broken'));
    const clock = mockClock();

    await useVideoQueueStore.getState().recordVideo({
      sourceUri: 'file:///tmp/clip.mp4',
      placeId: 'place-1',
      contentType: 'video/mp4',
      uploadedBy: 'user-a',
    });

    try {
      for (let i = 0; i < 5; i++) {
        await useVideoQueueStore.getState().runSyncPass('user-a');
        clock.advance(PAST_MAX_BACKOFF_MS);
      }

      const [video] = useVideoQueueStore.getState().videos;
      expect(video.syncState).toBe('failed');
      expect(video.attemptCount).toBe(5);
    } finally {
      clock.restore();
    }
  });

  it('retryFailedVideo resets a failed video back to recorded', async () => {
    (videosApi.requestVideoUpload as jest.Mock).mockRejectedValue(new Error('still broken'));
    const clock = mockClock();
    await useVideoQueueStore.getState().recordVideo({
      sourceUri: 'file:///tmp/clip.mp4',
      placeId: 'place-1',
      contentType: 'video/mp4',
      uploadedBy: 'user-a',
    });

    try {
      for (let i = 0; i < 5; i++) {
        await useVideoQueueStore.getState().runSyncPass('user-a');
        clock.advance(PAST_MAX_BACKOFF_MS);
      }
      const failedId = useVideoQueueStore.getState().videos[0].id;

      useVideoQueueStore.getState().retryFailedVideo(failedId);

      const video = useVideoQueueStore.getState().videos[0];
      expect(video.syncState).toBe('recorded');
      expect(video.attemptCount).toBe(0);
      expect(video.lastAttemptAt).toBeNull();
      expect(video.lastError).toBeNull();
    } finally {
      clock.restore();
    }
  });

  it('deleteFailedVideo removes the local file and the queue entry', async () => {
    (videosApi.requestVideoUpload as jest.Mock).mockRejectedValue(new Error('still broken'));
    const clock = mockClock();
    await useVideoQueueStore.getState().recordVideo({
      sourceUri: 'file:///tmp/clip.mp4',
      placeId: 'place-1',
      contentType: 'video/mp4',
      uploadedBy: 'user-a',
    });

    try {
      for (let i = 0; i < 5; i++) {
        await useVideoQueueStore.getState().runSyncPass('user-a');
        clock.advance(PAST_MAX_BACKOFF_MS);
      }
      const video = useVideoQueueStore.getState().videos[0];

      await useVideoQueueStore.getState().deleteFailedVideo(video.id);

      expect(FileSystem.deleteAsync).toHaveBeenCalledWith(video.localUri, { idempotent: true });
      expect(useVideoQueueStore.getState().videos).toHaveLength(0);
    } finally {
      clock.restore();
    }
  });

  it('deleteFailedVideo also dismisses a rejected video', async () => {
    (videosApi.requestVideoUpload as jest.Mock).mockResolvedValue({
      video_id: 'server-1', upload_url: 'https://r2.example.test/put', key: 'k',
    });
    (videosApi.uploadVideoToSignedUrl as jest.Mock).mockResolvedValue(undefined);
    (videosApi.confirmVideoUpload as jest.Mock).mockResolvedValue({ ok: true });

    const video = await useVideoQueueStore.getState().recordVideo({
      sourceUri: 'file:///tmp/clip.mp4', placeId: 'place-1', contentType: 'video/mp4', uploadedBy: 'user-a',
    });
    await useVideoQueueStore.getState().runSyncPass('user-a');
    useVideoQueueStore.getState().applyVideoReviewResult(video.id, 'rejected', 'No food visible');
    expect(useVideoQueueStore.getState().videos[0].syncState).toBe('rejected');

    await useVideoQueueStore.getState().deleteFailedVideo(video.id);
    expect(useVideoQueueStore.getState().videos).toHaveLength(0);
  });

  it('marks the queue entry missing_local_file rather than silently dropping it when the OS has removed the file', async () => {
    // Confirmed Phase 5 gap: previously this silently deleted the row --
    // the user's recording just vanished from the queue with no
    // explanation. A missing local file is a real, distinct terminal
    // failure, not the same as never having recorded anything.
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

    const [video] = useVideoQueueStore.getState().videos;
    expect(video.syncState).toBe('missing_local_file');
    expect(video.lastError).toBe('Local recording is no longer available.');
    expect(videosApi.uploadVideoToSignedUrl).not.toHaveBeenCalled();
    // Confirmed CodeRabbit finding on PR #134: the local-file check must
    // happen *before* requesting a backend upload slot -- otherwise
    // every missing-file video also left an orphaned `pending`
    // PlaceVideo row server-side for nothing.
    expect(videosApi.requestVideoUpload).not.toHaveBeenCalled();
  });

  it('bounds how many failed videos retain their local file, freeing the oldest ones past the retention cap', async () => {
    // Confirmed CodeRabbit finding on PR #134: excluding 'failed' from
    // MAX_QUEUED_VIDEOS (so a run of failures can't block new
    // recordings) otherwise let an unbounded number of them accumulate,
    // each still holding a real multi-MB file, with no UI to ever clear
    // them. MAX_RETAINED_FAILED_VIDEOS (3) bounds that: past it, the
    // oldest failed videos' local files are freed and folded into
    // missing_local_file.
    (videosApi.requestVideoUpload as jest.Mock).mockRejectedValue(new Error('still broken'));
    const clock = mockClock();

    try {
      const created = [];
      for (let i = 0; i < 5; i++) {
        created.push(
          await useVideoQueueStore.getState().recordVideo({
            sourceUri: `file:///tmp/clip-${i}.mp4`, placeId: 'place-1', contentType: 'video/mp4', uploadedBy: 'user-a',
          })
        );
        clock.advance(1_000); // distinct createdAt per video, oldest (clip-0) first
      }
      for (let i = 0; i < 5; i++) {
        await useVideoQueueStore.getState().runSyncPass('user-a');
        clock.advance(PAST_MAX_BACKOFF_MS);
      }

      const videos = useVideoQueueStore.getState().videos;
      const failed = videos.filter((v) => v.syncState === 'failed').map((v) => v.id).sort();
      const missing = videos.filter((v) => v.syncState === 'missing_local_file').map((v) => v.id).sort();
      // The 3 newest (clip-2, clip-3, clip-4) stay 'failed'; the 2
      // oldest (clip-0, clip-1) are pruned to 'missing_local_file'.
      expect(failed).toEqual([created[2].id, created[3].id, created[4].id].sort());
      expect(missing).toEqual([created[0].id, created[1].id].sort());
      expect(FileSystem.deleteAsync).toHaveBeenCalledWith(created[0].localUri, { idempotent: true });
      expect(FileSystem.deleteAsync).toHaveBeenCalledWith(created[1].localUri, { idempotent: true });
    } finally {
      clock.restore();
    }
  });

  it('keeps a video failed (not missing_local_file) when pruning cannot actually delete its file', async () => {
    // Confirmed CodeRabbit finding on PR #136: the prune loop previously
    // swallowed a deleteAsync rejection and still marked the video
    // missing_local_file regardless -- misrepresenting a file that may
    // still be on disk as gone, and permanently excluding it from any
    // future prune/retry since missing_local_file isn't 'failed'.
    (videosApi.requestVideoUpload as jest.Mock).mockRejectedValue(new Error('still broken'));
    (FileSystem.deleteAsync as jest.Mock).mockRejectedValueOnce(new Error('EACCES'));
    const clock = mockClock();

    try {
      const created = [];
      for (let i = 0; i < 4; i++) {
        created.push(
          await useVideoQueueStore.getState().recordVideo({
            sourceUri: `file:///tmp/clip-${i}.mp4`, placeId: 'place-1', contentType: 'video/mp4', uploadedBy: 'user-a',
          })
        );
        clock.advance(1_000);
      }
      for (let i = 0; i < 5; i++) {
        await useVideoQueueStore.getState().runSyncPass('user-a');
        clock.advance(PAST_MAX_BACKOFF_MS);
      }

      const videos = useVideoQueueStore.getState().videos;
      // clip-0 is the only prune candidate (4 failed - 3 retained = 1
      // overflow); its deletion was the one rejected above, so it must
      // stay 'failed', not be falsely folded into missing_local_file.
      const oldestId = created[0].id;
      const oldest = videos.find((v) => v.id === oldestId);
      expect(oldest?.syncState).toBe('failed');
      expect(videos.some((v) => v.syncState === 'missing_local_file')).toBe(false);
    } finally {
      clock.restore();
    }
  });

  it('does not retry a missing_local_file video on a later sync pass', async () => {
    (videosApi.requestVideoUpload as jest.Mock).mockResolvedValue({
      video_id: 'server-1', upload_url: 'https://r2.example.test/put', key: 'k',
    });
    (FileSystem.getInfoAsync as jest.Mock).mockResolvedValue({ exists: false });

    await useVideoQueueStore.getState().recordVideo({
      sourceUri: 'file:///tmp/clip.mp4', placeId: 'place-1', contentType: 'video/mp4', uploadedBy: 'user-a',
    });
    await useVideoQueueStore.getState().runSyncPass('user-a');
    (videosApi.requestVideoUpload as jest.Mock).mockClear();

    await useVideoQueueStore.getState().runSyncPass('user-a');
    expect(videosApi.requestVideoUpload).not.toHaveBeenCalled();
  });

  it('lets deleteFailedVideo clear a missing_local_file entry', async () => {
    (videosApi.requestVideoUpload as jest.Mock).mockResolvedValue({
      video_id: 'server-1', upload_url: 'https://r2.example.test/put', key: 'k',
    });
    (FileSystem.getInfoAsync as jest.Mock).mockResolvedValue({ exists: false });

    await useVideoQueueStore.getState().recordVideo({
      sourceUri: 'file:///tmp/clip.mp4', placeId: 'place-1', contentType: 'video/mp4', uploadedBy: 'user-a',
    });
    await useVideoQueueStore.getState().runSyncPass('user-a');
    const missing = useVideoQueueStore.getState().videos[0];

    await useVideoQueueStore.getState().deleteFailedVideo(missing.id);
    expect(useVideoQueueStore.getState().videos).toHaveLength(0);
  });

  it('does not let failed or missing-file videos permanently block new recordings against MAX_QUEUED_VIDEOS', async () => {
    // Both are terminal states nothing further will happen to without an
    // explicit delete -- they shouldn't count as "actively waiting to
    // post" and lock a user out of recording anything new ever again.
    (videosApi.requestVideoUpload as jest.Mock).mockRejectedValue(new Error('still broken'));
    const clock = mockClock();

    try {
      // Drive 10 videos to the 'failed' terminal state (MAX_ATTEMPTS).
      for (let i = 0; i < 10; i++) {
        await useVideoQueueStore.getState().recordVideo({
          sourceUri: `file:///tmp/clip-${i}.mp4`, placeId: 'place-1', contentType: 'video/mp4', uploadedBy: 'user-a',
        });
      }
      for (let i = 0; i < 5; i++) {
        await useVideoQueueStore.getState().runSyncPass('user-a');
        clock.advance(PAST_MAX_BACKOFF_MS);
      }
      // All 10 reached a terminal state -- some stay 'failed' (their
      // local file retained, up to MAX_RETAINED_FAILED_VIDEOS), the rest
      // pruned to 'missing_local_file' (file freed) once that cap was
      // exceeded. Either way, none are still actively retrying.
      expect(
        useVideoQueueStore.getState().videos.every(
          (v) => v.syncState === 'failed' || v.syncState === 'missing_local_file'
        )
      ).toBe(true);

      // A new recording must still be accepted -- none of the 10 above
      // are "actively waiting to post" anymore.
      await expect(
        useVideoQueueStore.getState().recordVideo({
          sourceUri: 'file:///tmp/one-more.mp4', placeId: 'place-1', contentType: 'video/mp4', uploadedBy: 'user-a',
        })
      ).resolves.toBeTruthy();
    } finally {
      clock.restore();
    }
  });
});

// Its own top-level describe (not nested in the main one above) since it
// needs to control what AsyncStorage.getItem resolves to *before* the
// store module is first required, rather than reusing the shared
// beforeEach's fixed empty-storage setup.
describe('videoQueueStore persisted-store migration', () => {
  it('migrates a legacy persisted "synced" video (uploaded before this version tracked review outcomes) to reviewing, not silently treating it as approved', async () => {
    // Confirmed CodeRabbit finding on PR #310: a device already holding a
    // 'synced' row from before this version shipped would otherwise have
    // it pruned as "approved" on the very next sync pass -- with no
    // chance to ever learn of a real rejection the backend might still
    // hand back for it.
    jest.resetModules();
    const AsyncStorageModule = require('@react-native-async-storage/async-storage').default;
    const legacyPersistedState = JSON.stringify({
      state: {
        videos: [
          {
            id: 'legacy-1', serverId: 'server-legacy', localUri: 'file:///legacy.mp4',
            placeId: 'place-1', templateId: null, contentType: 'video/mp4', uploadedBy: 'user-a',
            syncState: 'synced', attemptCount: 0, lastAttemptAt: null, lastError: null, createdAt: 1,
          },
          // A video with no serverId was never actually uploaded under any
          // version -- shouldn't exist in practice, but must pass through
          // unmigrated (not force-converted into a nonsensical 'reviewing'
          // state with nothing to poll).
          {
            id: 'legacy-2', serverId: null, localUri: 'file:///legacy2.mp4',
            placeId: 'place-1', templateId: null, contentType: 'video/mp4', uploadedBy: 'user-a',
            syncState: 'recorded', attemptCount: 0, lastAttemptAt: null, lastError: null, createdAt: 2,
          },
        ],
      },
      version: 0,
    });
    // Keyed by storage name, not a blind "next call" -- videoQueueStore.ts
    // now also imports uploadPreferencesStore.ts, whose own persist
    // middleware calls getItem('crave-upload-preferences') during the
    // same require() below, and a plain mockResolvedValueOnce would get
    // consumed by whichever store's rehydration happens to run first.
    (AsyncStorageModule.getItem as jest.Mock).mockImplementation((key: string) =>
      Promise.resolve(key === 'crave-video-queue' ? legacyPersistedState : null)
    );

    const { useVideoQueueStore: migratedStore } = require('./videoQueueStore');
    for (let i = 0; i < 15; i++) {
      await Promise.resolve();
    }

    const videos = migratedStore.getState().videos;
    expect(videos.find((v: { id: string }) => v.id === 'legacy-1')?.syncState).toBe('reviewing');
    expect(videos.find((v: { id: string }) => v.id === 'legacy-2')?.syncState).toBe('recorded');
  });

  it('waits for uploadPreferencesStore to finish hydrating before trusting its default wifiOnlyVideoUploads value', async () => {
    // Confirmed CodeRabbit finding on PR #312: uploadPreferencesStore's
    // `false` default is live the instant its module loads, but the real
    // persisted value only lands once AsyncStorage's own rehydration
    // resolves -- a genuine async gap. Without awaiting it, a foreground/
    // connectivity event that fires runSyncPass early enough would read
    // the still-default `false` and upload a video over cellular despite
    // the user having turned Wi-Fi-only on.
    jest.resetModules();
    const AsyncStorageModule = require('@react-native-async-storage/async-storage').default;

    let resolveUploadPrefsGetItem: (value: string | null) => void = () => {};
    const uploadPrefsGetItemPromise = new Promise<string | null>((resolve) => {
      resolveUploadPrefsGetItem = resolve;
    });
    (AsyncStorageModule.getItem as jest.Mock).mockImplementation((key: string) =>
      key === 'crave-upload-preferences' ? uploadPrefsGetItemPromise : Promise.resolve(null)
    );

    const { useVideoQueueStore: freshStore } = require('./videoQueueStore');
    const videosApiFresh = require('../api/videos');
    (videosApiFresh.requestVideoUpload as jest.Mock).mockResolvedValue({
      video_id: 'server-1', upload_url: 'https://r2.example.test/put', key: 'k',
    });
    (videosApiFresh.uploadVideoToSignedUrl as jest.Mock).mockResolvedValue(undefined);
    (videosApiFresh.confirmVideoUpload as jest.Mock).mockResolvedValue({ ok: true });
    const NetInfoFresh = require('@react-native-community/netinfo').default;
    (NetInfoFresh.fetch as jest.Mock).mockResolvedValue({
      type: 'cellular', isConnected: true, isInternetReachable: true, details: {},
    });

    await freshStore.getState().recordVideo({
      sourceUri: 'file:///tmp/clip.mp4', placeId: 'place-1', contentType: 'video/mp4', uploadedBy: 'user-a',
    });

    const syncPromise = freshStore.getState().runSyncPass('user-a');

    // uploadPreferencesStore hasn't rehydrated yet -- without the fix,
    // runSyncPass would already have read the default `false` and
    // requested an upload slot over cellular by now.
    for (let i = 0; i < 15; i++) {
      await Promise.resolve();
    }
    expect(videosApiFresh.requestVideoUpload).not.toHaveBeenCalled();

    // Now rehydration resolves with the user's real, persisted `true`.
    resolveUploadPrefsGetItem(JSON.stringify({ state: { wifiOnlyVideoUploads: true }, version: 0 }));
    await syncPromise;

    expect(videosApiFresh.requestVideoUpload).not.toHaveBeenCalled();
    expect(freshStore.getState().videos[0].syncState).toBe('recorded');
  });
});
