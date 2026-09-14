// videoQueueStore.ts
//
// Offline "record now, upload later" queue for the short food-video
// feature. Mirrors cravesStore.ts's offline-outbox pattern (this session
// already built and tested that exact shape for saves): record locally
// first, sync when connectivity returns, never let a lost network call
// lose the user's recording.
//
// Ported from a reference implementation built for a standalone Node.js
// backend using expo-sqlite -- rebuilt here against Zustand + AsyncStorage
// instead, matching every other store in this app (cravesStore.ts,
// cityStore.ts) rather than introducing a new persistence dependency for
// what's realistically a handful of queued items at a time.
import { AppState } from 'react-native';
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
// SDK54's expo-file-system replaced its promise-based API with a new
// class-based one (File/Directory) at the default import path -- the
// familiar documentDirectory/moveAsync/getInfoAsync/deleteAsync surface
// this file is written against still exists, just moved to this
// /legacy subpath. Still fully supported, not a deprecated dead end.
import * as FileSystem from 'expo-file-system/legacy';

import {
  requestVideoUpload,
  confirmVideoUpload,
  uploadVideoToSignedUrl,
  VideoContentType,
  VideoStatus,
} from '../api/videos';

export type VideoSyncState =
  | 'recorded'
  | 'requesting_url'
  | 'uploading'
  | 'completing'
  // Uploaded and confirmed, but not yet visible anywhere -- the backend's
  // separate scheduler-driven worker (video_processing_worker.py) still
  // has to compress/food-score/moderate it before it's approved or
  // rejected. Distinct from 'synced': that now means "approved," reached
  // only via applyVideoReviewResult below once polling confirms it, not
  // the instant the upload itself completes.
  | 'reviewing'
  | 'synced'
  // The backend moderated it and it did not pass -- distinct from
  // 'failed' (an upload/network failure, retryable) since resubmitting
  // the same rejected content would just be rejected again. Dismissible
  // via deleteFailedVideo, not retryable.
  | 'rejected'
  | 'failed' // only after MAX_ATTEMPTS is exhausted
  | 'missing_local_file'; // terminal -- the recorded file itself is gone, nothing left to upload

export interface QueuedVideo {
  id: string; // client-generated -- doubles as the client_id sent to the backend
  serverId: string | null; // filled in once /videos/request succeeds
  localUri: string;
  placeId: string;
  templateId: string | null;
  contentType: VideoContentType;
  uploadedBy: string; // the signed-in user id at record time -- see below
  syncState: VideoSyncState;
  attemptCount: number;
  // Timestamp of the most recent sync attempt, or null if never attempted
  // (or reset by retryFailedVideo). Drives the exponential backoff below
  // -- without it, runSyncPass retried every queued video on every
  // foreground/reconnect event regardless of how recently it had just
  // failed, which for a real multi-MB upload (not cravesStore's tiny JSON
  // outbox) means repeatedly re-attempting a large PUT against a
  // connection that was just proven bad seconds ago.
  lastAttemptAt: number | null;
  lastError: string | null;
  createdAt: number;
  // 0-1 fraction reported by uploadVideoToSignedUrl's onProgress while
  // syncState === 'uploading'; null the rest of the time (never started,
  // or past the upload step entirely) so a stale value from a previous
  // attempt can't be mistaken for current progress.
  uploadProgress: number | null;
}

const MAX_ATTEMPTS = 5;

// Same formula and reasoning as cravesStore.ts's own backoff (see its
// comment) -- 5s, 10s, 20s, 40s... capped at 5 minutes, computed from
// lastAttemptAt rather than createdAt.
const BACKOFF_BASE_MS = 5_000;
const BACKOFF_MAX_MS = 5 * 60_000;

function backoffDelayMs(attemptCount: number): number {
  return Math.min(BACKOFF_MAX_MS, BACKOFF_BASE_MS * 2 ** Math.max(0, attemptCount - 1));
}

function isReadyToRetry(video: QueuedVideo, now: number): boolean {
  if (video.attemptCount <= 0 || video.lastAttemptAt == null) return true;
  return now - video.lastAttemptAt >= backoffDelayMs(video.attemptCount);
}
const MAX_QUEUED_VIDEOS = 10;
// Videos are real, multi-MB files -- a fixed cap here matters far more
// than for cravesStore's tiny JSON-only outbox entries, both for on-
// device storage and because a runaway queue would mean a very long
// backlog to drain once connectivity returns.

// A 'failed' video (unlike 'missing_local_file') still retains its real,
// full local file -- that's the whole point, so retryFailedVideo has
// something to resubmit. Excluding it from MAX_QUEUED_VIDEOS (so it
// can't permanently block new recordings) would otherwise let an
// unbounded number of them accumulate with no UI to ever clear them,
// each still holding a multi-MB file. This caps how many are *retained*
// -- once exceeded, the oldest failed video's local file is deleted
// (freeing the storage) and it's folded into missing_local_file, which
// accurately describes it from that point on: retryable in principle,
// but the file itself is now actually gone.
const MAX_RETAINED_FAILED_VIDEOS = 3;

function generateLocalId(): string {
  // Not cryptographically secure -- doesn't need to be. This is purely a
  // local idempotency key (see backend routes/videos.py's client_id
  // dedupe), never a security boundary.
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

const PENDING_CLIPS_DIR = `${FileSystem.documentDirectory}pending_video_clips/`;

interface VideoQueueStore {
  videos: QueuedVideo[];

  // Step 1: save locally, no network involved. Moves (not copies) the
  // camera's temp output into a stable app-owned directory so it
  // survives even if the OS clears the camera's own temp dir.
  recordVideo: (opts: {
    sourceUri: string;
    placeId: string;
    contentType: VideoContentType;
    uploadedBy: string;
    templateId?: string | null;
  }) => Promise<QueuedVideo>;

  // Step 2: drain the queue for `userId` -- only videos recorded while
  // that same user was signed in are attempted. A video recorded by a
  // different (not-currently-signed-in) account stays queued untouched
  // until that account signs back in and calls this again -- the same
  // account-scoping problem, and the same fix, as cravesStore's
  // pendingSyncActions: every outbound call authenticates as whoever is
  // CURRENTLY signed in (see src/api/client.ts's session-token
  // interceptor), so syncing another account's queued video here would
  // silently attribute it to the wrong user.
  runSyncPass: (userId: string) => Promise<void>;

  retryFailedVideo: (id: string) => void;
  deleteFailedVideo: (id: string) => Promise<void>;

  // Called by useVideoStatusPoll (see that hook) once a 'reviewing'
  // video's backend moderation outcome is known. 'approved' resolves to
  // 'synced' -- the existing prune-on-next-pass logic then clears it
  // exactly as it already does for any other synced video, no separate
  // cleanup path needed. A non-approved terminal outcome resolves to
  // 'rejected', which -- unlike 'synced' -- is never auto-pruned, so the
  // user actually sees why before dismissing it themselves.
  applyVideoReviewResult: (id: string, status: VideoStatus, rejectReason: string | null) => void;
}

let syncInFlight = false;

export const useVideoQueueStore = create<VideoQueueStore>()(
  persist(
    (set, get) => ({
      videos: [],

      recordVideo: async ({ sourceUri, placeId, contentType, uploadedBy, templateId }) => {
        // 'failed' and 'missing_local_file' are both terminal -- nothing
        // further will happen to them without an explicit user action
        // (retryFailedVideo/deleteFailedVideo), so they shouldn't count
        // against the "how many are actively waiting to post" cap and
        // permanently block new recordings just because an old one
        // stalled out.
        const queuedCount = get().videos.filter(
          (v) =>
            v.syncState !== 'synced' &&
            v.syncState !== 'reviewing' &&
            v.syncState !== 'rejected' &&
            v.syncState !== 'failed' &&
            v.syncState !== 'missing_local_file'
        ).length;
        if (queuedCount >= MAX_QUEUED_VIDEOS) {
          throw new Error(
            `You have ${queuedCount} videos waiting to post. Connect to wifi or clear a ` +
              `failed video from your queue before recording another.`
          );
        }

        await FileSystem.makeDirectoryAsync(PENDING_CLIPS_DIR, { intermediates: true }).catch(
          () => {}
        );

        const id = generateLocalId();
        const ext = contentType === 'video/quicktime' ? 'mov' : contentType === 'video/webm' ? 'webm' : 'mp4';
        const destUri = `${PENDING_CLIPS_DIR}${id}.${ext}`;
        await FileSystem.moveAsync({ from: sourceUri, to: destUri });

        const video: QueuedVideo = {
          id,
          serverId: null,
          localUri: destUri,
          placeId,
          templateId: templateId ?? null,
          contentType,
          uploadedBy,
          syncState: 'recorded',
          attemptCount: 0,
          lastAttemptAt: null,
          lastError: null,
          createdAt: Date.now(),
          uploadProgress: null,
        };

        set({ videos: [video, ...get().videos] });
        return video;
      },

      runSyncPass: async (userId: string) => {
        if (syncInFlight) return;
        syncInFlight = true;
        try {
          // A video that synced successfully in a *prior* pass has already
          // had its local file deleted (see syncOne below) and nothing in
          // the app ever reads a 'synced' entry back out of this store
          // (PlaceVideoGallery doesn't consume this store at all) -- so
          // without this, every successful upload left a dead row in the
          // AsyncStorage-persisted `videos` array forever, growing without
          // bound. Pruned here, at the *start* of the pass rather than the
          // instant syncOne marks a video 'synced', so a caller that just
          // awaited runSyncPass and inspected the video it synced this same
          // call (see videoQueueStore.test.ts) still finds it.
          await pruneSyncedVideos(set, get);

          const now = Date.now();
          const pending = get().videos.filter(
            (v) =>
              v.uploadedBy === userId &&
              v.syncState !== 'synced' &&
              v.syncState !== 'reviewing' &&
              v.syncState !== 'rejected' &&
              v.syncState !== 'failed' &&
              v.syncState !== 'missing_local_file' &&
              v.attemptCount < MAX_ATTEMPTS &&
              isReadyToRetry(v, now)
          );

          for (const video of pending) {
            try {
              await syncOne(video, set, get);
            } catch (err: any) {
              await recordFailure(video.id, err?.message ?? String(err), set, get);
              // Keep going -- one bad video shouldn't block the rest of the queue.
            }
          }
        } finally {
          syncInFlight = false;
        }
      },

      retryFailedVideo: (id: string) => {
        set({
          videos: get().videos.map((v) =>
            v.id === id && v.syncState === 'failed'
              ? {
                  ...v,
                  syncState: 'recorded',
                  attemptCount: 0,
                  lastAttemptAt: null,
                  lastError: null,
                  uploadProgress: null,
                }
              : v
          ),
        });
      },

      deleteFailedVideo: async (id: string) => {
        const video = get().videos.find((v) => v.id === id);
        // All three are equally unrecoverable and equally safe to clear --
        // 'failed' (retries exhausted) and 'missing_local_file' still have
        // (or once had) a local file, while 'rejected' never does by this
        // point (syncOne already deleted it on successful upload) --
        // deleteAsync is idempotent regardless of whether the file exists.
        if (
          !video ||
          (video.syncState !== 'failed' &&
            video.syncState !== 'missing_local_file' &&
            video.syncState !== 'rejected')
        ) {
          return;
        }
        await FileSystem.deleteAsync(video.localUri, { idempotent: true }).catch(() => {});
        set({ videos: get().videos.filter((v) => v.id !== id) });
      },

      applyVideoReviewResult: (id: string, status: VideoStatus, rejectReason: string | null) => {
        set({
          videos: get().videos.map((v) => {
            if (v.id !== id || v.syncState !== 'reviewing') return v;
            if (status === 'approved') {
              return { ...v, syncState: 'synced', lastError: null };
            }
            if (status === 'rejected' || status === 'failed') {
              return {
                ...v,
                syncState: 'rejected',
                lastError: rejectReason ?? 'This video was not approved.',
              };
            }
            // 'pending' / 'queued' / 'processing' -- still under review,
            // nothing to change yet; the poll hook keeps calling this as
            // status updates arrive.
            return v;
          }),
        });
      },
    }),
    {
      name: 'crave-video-queue',
      storage: createJSONStorage(() => AsyncStorage),
      // Confirmed CodeRabbit finding on PR #310: before this version,
      // 'synced' meant only "upload confirmed" -- a device that already
      // has a persisted 'synced' row from before this update shipped
      // would, on the first rehydration under the new code, be treated
      // as already-approved (the new meaning of 'synced') and pruned on
      // the very next sync pass, with no chance to ever see a real
      // rejection the backend might still hand back for it. Migrating
      // any such legacy row (uploaded, so it has a serverId) to
      // 'reviewing' lets the normal poll path resolve its actual outcome
      // instead of silently assuming success.
      version: 1,
      migrate: (persistedState: unknown, version: number) => {
        const state = (persistedState ?? {}) as { videos?: unknown };
        const videos = Array.isArray(state.videos) ? state.videos : [];
        // uploadProgress was added after version 1 shipped, so any legacy
        // persisted row (regardless of which branch below touches it) may
        // be missing the field entirely -- backfilled to null rather than
        // left undefined so it matches the QueuedVideo type exactly.
        const withProgress = (video: QueuedVideo): QueuedVideo => ({
          ...video,
          uploadProgress: video.uploadProgress ?? null,
        });
        if (version >= 1) {
          return { ...state, videos: videos.map((v) => withProgress(v as QueuedVideo)) };
        }
        return {
          ...state,
          videos: videos.map((v) => {
            const video = v as QueuedVideo;
            const migrated =
              video && video.syncState === 'synced' && video.serverId
                ? { ...video, syncState: 'reviewing' as const }
                : video;
            return withProgress(migrated);
          }),
        };
      },
    }
  )
);

async function syncOne(
  video: QueuedVideo,
  set: (partial: Partial<VideoQueueStore>) => void,
  get: () => VideoQueueStore
) {
  const setVideoState = (patch: Partial<QueuedVideo>) => {
    set({
      videos: get().videos.map((v) => (v.id === video.id ? { ...v, ...patch } : v)),
    });
  };

  // Checked *before* ever contacting the backend -- requesting an upload
  // slot creates a real `pending` PlaceVideo row server-side (see
  // request_video_upload_slot), so checking the local file only after
  // that call meant every missing-file video also left an orphaned
  // pending row behind for no reason (it can never be confirmed, since
  // there's nothing left to upload).
  const fileInfo = await FileSystem.getInfoAsync(video.localUri);
  if (!fileInfo.exists) {
    // Local file is gone (user cleared storage, an OS cache sweep, etc.)
    // -- nothing to upload, no recovering it. Previously this silently
    // dropped the row entirely, so the user's recording just vanished
    // from the queue with no explanation at all. A missing local file is
    // a real, distinct terminal failure -- not the same as never having
    // recorded anything -- so it's recorded as one instead of erased.
    setVideoState({ syncState: 'missing_local_file', lastError: 'Local recording is no longer available.' });
    return;
  }

  // Always (re-)request an upload URL, even if serverId is already set --
  // the presigned URL itself is never persisted (only the server row id
  // is), and a fresh URL is needed on every attempt regardless. The
  // backend's client_id dedupe (see routes/videos.py) makes this safe and
  // idempotent: a repeat call for the same video.id returns the same
  // server row and storage key rather than creating a duplicate.
  setVideoState({ syncState: 'requesting_url' });
  const { video_id: serverId, upload_url: uploadUrl } = await requestVideoUpload({
    place_id: video.placeId,
    content_type: video.contentType,
    template_id: video.templateId ?? undefined,
    client_id: video.id,
  });
  setVideoState({ serverId });

  setVideoState({ syncState: 'uploading', uploadProgress: 0 });
  await uploadVideoToSignedUrl(uploadUrl, video.localUri, video.contentType, (fraction) => {
    setVideoState({ uploadProgress: fraction });
  });

  setVideoState({ syncState: 'completing', uploadProgress: null });
  await confirmVideoUpload(serverId);

  // Uploaded and confirmed -- the local file's job is done regardless of
  // what the backend's moderation review eventually decides, so it's
  // freed here rather than held until that (possibly much later) outcome
  // is known. 'reviewing', not 'synced': the review itself hasn't
  // happened yet (see applyVideoReviewResult, driven by
  // useVideoStatusPoll).
  setVideoState({ syncState: 'reviewing' });
  await FileSystem.deleteAsync(video.localUri, { idempotent: true }).catch(() => {});
}

async function recordFailure(
  id: string,
  message: string,
  set: (partial: Partial<VideoQueueStore>) => void,
  get: () => VideoQueueStore
) {
  set({
    videos: get().videos.map((v) => {
      if (v.id !== id) return v;
      const attemptCount = v.attemptCount + 1;
      return {
        ...v,
        attemptCount,
        lastAttemptAt: Date.now(),
        lastError: message,
        syncState: attemptCount >= MAX_ATTEMPTS ? 'failed' : 'recorded',
        uploadProgress: null,
      };
    }),
  });
  await pruneRetainedFailedVideos(set, get);
}

// syncOne already attempted FileSystem.deleteAsync once and silently
// swallowed a real failure (see its own comment) -- if that attempt
// genuinely failed (not just "already gone," which idempotent:true
// already treats as success), the video was still marked 'synced'
// regardless. Blindly pruning every 'synced' row here would then
// silently lose the last reference to a real, still-on-disk orphaned
// file forever (confirmed CodeRabbit finding on PR #307). Retrying the
// (idempotent, so safe to repeat) delete here means a row is only
// removed once its file is actually gone; a still-failing delete keeps
// the row -- and its localUri -- around for the next pass to retry.
async function pruneSyncedVideos(
  set: (partial: Partial<VideoQueueStore>) => void,
  get: () => VideoQueueStore
) {
  const synced = get().videos.filter((v) => v.syncState === 'synced');
  if (synced.length === 0) return;

  const stillOrphaned = new Set<string>();
  for (const video of synced) {
    try {
      await FileSystem.deleteAsync(video.localUri, { idempotent: true });
    } catch {
      stillOrphaned.add(video.id);
    }
  }

  set({
    videos: get().videos.filter((v) => v.syncState !== 'synced' || stillOrphaned.has(v.id)),
  });
}

// A 'failed' video retains its real local file (unlike
// 'missing_local_file'), and with no queue-management UI to ever
// explicitly delete one, an unbounded number could otherwise pile up --
// each a real multi-MB file -- since Phase 5 deliberately excluded
// 'failed' from MAX_QUEUED_VIDEOS so a run of failures couldn't
// permanently block new recordings. This bounds that the other way:
// once more than MAX_RETAINED_FAILED_VIDEOS have accumulated, the
// oldest ones' local files are freed and folded into
// missing_local_file, which is simply the truth from that point on.
async function pruneRetainedFailedVideos(
  set: (partial: Partial<VideoQueueStore>) => void,
  get: () => VideoQueueStore
) {
  const failed = get()
    .videos.filter((v) => v.syncState === 'failed')
    .sort((a, b) => a.createdAt - b.createdAt);
  const overflow = failed.length - MAX_RETAINED_FAILED_VIDEOS;
  if (overflow <= 0) return;

  for (const video of failed.slice(0, overflow)) {
    try {
      await FileSystem.deleteAsync(video.localUri, { idempotent: true });
    } catch {
      // Deletion genuinely failed (not just "already gone" -- that's
      // what idempotent:true is for) -- the file may still be on disk,
      // so leave this video 'failed' rather than falsely claiming
      // missing_local_file. It stays counted for the next prune pass.
      continue;
    }
    set({
      videos: get().videos.map((v) =>
        v.id === video.id
          ? { ...v, syncState: 'missing_local_file', lastError: 'Local recording is no longer available.' }
          : v
      ),
    });
  }
}

// Foreground trigger -- mirrors cravesStore.ts's own AppState listener.
// Callers still need to invoke runSyncPass(userId) themselves once on
// mount/sign-in (there's no way to know "which user" from this listener
// alone) -- this only covers "the app was already showing a signed-in
// user and came back to the foreground."
let _currentUserIdForForegroundSync: string | null = null;

export function setActiveUserForVideoSync(userId: string | null): void {
  _currentUserIdForForegroundSync = userId;
}

AppState.addEventListener('change', (state) => {
  if (state !== 'active') return;
  if (!_currentUserIdForForegroundSync) return;
  useVideoQueueStore.getState().runSyncPass(_currentUserIdForForegroundSync).catch(() => {});
});
