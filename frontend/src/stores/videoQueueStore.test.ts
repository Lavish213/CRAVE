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
