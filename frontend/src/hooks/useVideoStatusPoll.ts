import { useEffect, useState } from 'react';
import { fetchVideoStatus, VideoStatus } from '../api/videos';

export const useVideoStatusPoll = (videoId?: string) => {
  const [status, setStatus] = useState<VideoStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState<string | null>(null);

  useEffect(() => {
    if (!videoId) return undefined;

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
        setError(res.status === 'failed' ? res.rejectReason ?? 'Video processing failed.' : null);

        if (res.status === 'approved' || res.status === 'rejected' || res.status === 'failed') {
          return;
        }

        delay = Math.min(delay + 2000, 10000);
        timer = setTimeout(poll, delay);
      } catch (err) {
        if (__DEV__) console.error('[VIDEO POLL ERROR]', err);
        if (!active) return;
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

  return { status, error, rejectReason };
};
