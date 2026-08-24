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
} from '../api/videos';

export type VideoSyncState =
  | 'recorded'
  | 'requesting_url'
  | 'uploading'
  | 'completing'
  | 'synced'
  | 'failed'; // only after MAX_ATTEMPTS is exhausted

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
}

let syncInFlight = false;

export const useVideoQueueStore = create<VideoQueueStore>()(
  persist(
    (set, get) => ({
      videos: [],

      recordVideo: async ({ sourceUri, placeId, contentType, uploadedBy, templateId }) => {
        const queuedCount = get().videos.filter((v) => v.syncState !== 'synced').length;
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
        };

        set({ videos: [video, ...get().videos] });
        return video;
      },

      runSyncPass: async (userId: string) => {
        if (syncInFlight) return;
        syncInFlight = true;
        try {
          const now = Date.now();
          const pending = get().videos.filter(
            (v) =>
              v.uploadedBy === userId &&
              v.syncState !== 'synced' &&
              v.syncState !== 'failed' &&
              v.attemptCount < MAX_ATTEMPTS &&
              isReadyToRetry(v, now)
          );

          for (const video of pending) {
            try {
              await syncOne(video, set, get);
            } catch (err: any) {
              recordFailure(video.id, err?.message ?? String(err), set, get);
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
              ? { ...v, syncState: 'recorded', attemptCount: 0, lastAttemptAt: null, lastError: null }
              : v
          ),
        });
      },

      deleteFailedVideo: async (id: string) => {
        const video = get().videos.find((v) => v.id === id);
        if (!video || video.syncState !== 'failed') return;
        await FileSystem.deleteAsync(video.localUri, { idempotent: true }).catch(() => {});
        set({ videos: get().videos.filter((v) => v.id !== id) });
      },
    }),
    {
      name: 'crave-video-queue',
      storage: createJSONStorage(() => AsyncStorage),
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

  const fileInfo = await FileSystem.getInfoAsync(video.localUri);
  if (!fileInfo.exists) {
    // Local file is gone (user cleared storage, etc.) -- nothing to
    // upload, no recovering it. Drop the row entirely.
    set({ videos: get().videos.filter((v) => v.id !== video.id) });
    return;
  }

  setVideoState({ syncState: 'uploading' });
  await uploadVideoToSignedUrl(uploadUrl, video.localUri, video.contentType);

  setVideoState({ syncState: 'completing' });
  await confirmVideoUpload(serverId);

  setVideoState({ syncState: 'synced' });
  await FileSystem.deleteAsync(video.localUri, { idempotent: true }).catch(() => {});
}

function recordFailure(
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
      };
    }),
  });
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
