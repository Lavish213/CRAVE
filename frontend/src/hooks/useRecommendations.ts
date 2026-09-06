// src/hooks/useRecommendations.ts
//
// Personalized recommendations. `enabled` lets a hidden/feature-flagged
// consumer preserve hook ordering without performing background network work.
import { useCallback, useEffect, useRef, useState } from 'react';
import { PlaceOut, fetchRecommendations } from '../api/places';
import { useAuthStore } from '../stores/authStore';

export function useRecommendations(enabled = true): PlaceOut[] {
  const user = useAuthStore((s) => s.user);
  const [recommendations, setRecommendations] = useState<PlaceOut[]>([]);
  const requestIdRef = useRef(0);

  const load = useCallback(() => {
    const requestId = ++requestIdRef.current;
    fetchRecommendations()
      .then((data) => {
        if (requestId !== requestIdRef.current) return;
        setRecommendations(data);
      })
      .catch((err: unknown) => {
        if (!__DEV__) return;
        const status = typeof err === 'object' && err !== null && 'response' in err
          ? (err as { response?: { status?: number } }).response?.status
          : undefined;
        const message = err instanceof Error ? err.message : String(err);
        console.warn('[useRecommendations] fetch_failed', status, message);
      });
  }, []);

  useEffect(() => {
    if (!enabled || !user?.id) {
      requestIdRef.current += 1;
      setRecommendations([]);
      return;
    }
    load();
  }, [enabled, user?.id, load]);

  return enabled ? recommendations : [];
}
