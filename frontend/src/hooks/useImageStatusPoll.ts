import { useEffect, useState } from 'react';
import { fetchUploadStatus, UploadStatus } from '../api/upload';

export const useImageStatusPoll = (imageId?: string) => {
  const [status, setStatus] = useState<UploadStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!imageId) return;

    let active = true;
    let delay = 2000;
    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      if (!active) return;

      try {
        const res = await fetchUploadStatus(imageId);
        if (!active) return;

        setStatus(res.status);
        if (res.error) setError(res.error);

        if (res.status === 'ready' || res.status === 'failed') {
          return;
        }

        delay = Math.min(delay + 2000, 10000);
        timer = setTimeout(poll, delay);
      } catch (err) {
        if (__DEV__) console.error('[POLL ERROR]', err);
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
  }, [imageId]);

  return { status, error };
};
