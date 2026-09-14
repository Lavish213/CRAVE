// useVideoStatusPoll.ts
//
// Mirrors useImageStatusPoll.ts's polling shape, applied to a video's
// backend moderation review instead of an image's. A video's own upload
// (videoQueueStore.ts) is entirely local-queue-driven and can finish at
// any time -- offline, in the background, long after whatever screen
// recorded it has closed -- so this hook is meant to be mounted by
// whatever screen is showing a 'reviewing' video (the Uploads screen),
// not the record-video screen itself.
import { useEffect, useState } from 'react';
import { fetchVideoStatus, VideoStatus } from '../api/videos';

export function useVideoStatusPoll(videoId?: string | null) {
  const [status, setStatus] = useState<VideoStatus | null>(null);
  const [rejectReason, setRejectReason] = useState<string | null>(null);
  // Confirmed CodeRabbit finding on PR #310: a persistently-failing
  // fetchVideoStatus call (e.g. genuinely offline) retried forever with
  // nothing surfaced -- the caller had no way to tell "still checking"
  // apart from "hasn't been able to check in a while." Cleared on every
  // successful response, including a still-processing one, so a
  // transient blip doesn't leave stale error text sitting on screen once
  // polling recovers.
  const [pollError, setPollError] = useState<string | null>(null);

  useEffect(() => {
    if (!videoId) return;

    let active = true;
    let delay = 2000;
    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      if (!active) return;

      try {
        const res = await fetchVideoStatus(videoId);
        if (!active) return;

        setStatus(res.status);
        setRejectReason(res.rejectReason);
        setPollError(null);

        if (res.status === 'approved' || res.status === 'rejected' || res.status === 'failed') {
          return;
        }

        delay = Math.min(delay + 2000, 10000);
        timer = setTimeout(poll, delay);
      } catch (err) {
        if (__DEV__) console.error('[VIDEO POLL ERROR]', err);
        if (!active) return;
        setPollError(err instanceof Error ? err.message : "Couldn't check this video's status.");
        delay = Math.min(delay + 2000, 10000);
        timer = setTimeout(poll, delay);
      }
    };

    poll();

    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [videoId]);

  return { status, rejectReason, pollError };
}
