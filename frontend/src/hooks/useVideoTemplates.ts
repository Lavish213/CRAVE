// src/hooks/useVideoTemplates.ts
//
// Active shot templates for the video record screen (e.g. "Cheese Pull",
// "First Cut") -- data-driven on the backend (see
// backend/app/db/models/video_template.py), so this hook just reflects
// whatever's active server-side rather than hardcoding a list.
import { useEffect, useState } from 'react';
import { VideoTemplate, fetchVideoTemplates } from '../api/videos';

export function useVideoTemplates(): { templates: VideoTemplate[]; loading: boolean } {
  const [templates, setTemplates] = useState<VideoTemplate[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetchVideoTemplates()
      .then((data) => {
        if (cancelled) return;
        setTemplates(data.templates);
      })
      .catch((err: any) => {
        if (__DEV__) console.warn('[useVideoTemplates] fetch_failed', err?.response?.status, err?.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { templates, loading };
}
