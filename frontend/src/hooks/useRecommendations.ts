// src/hooks/useRecommendations.ts
//
// "For You" personalized recommendations (Beli's "prediction score" feed)
// -- same shape as useTrending.ts, keyed on the signed-in user instead of
// the selected city. Requires auth, so this returns [] whenever signed
// out rather than hitting the backend (which would 401).
import { useCallback, useEffect, useRef, useState } from 'react';
import { PlaceOut, fetchRecommendations } from '../api/places';
import { useAuthStore } from '../stores/authStore';

export function useRecommendations(): PlaceOut[] {
  const user = useAuthStore((s) => s.user);
  const [recommendations, setRecommendations] = useState<PlaceOut[]>([]);

  // Generation-ref guard against a stale response landing after a
  // sign-out/sign-in-as-different-account -- same pattern as
  // cravesStore.ts's account-switch guard.
  const requestIdRef = useRef(0);

  const load = useCallback((userId: string) => {
    const requestId = ++requestIdRef.current;
    fetchRecommendations()
      .then((data) => {
        if (requestId !== requestIdRef.current) return;
        setRecommendations(data);
      })
      .catch((err: any) => {
        // Non-critical, nice-to-have row -- fail silently for the user,
        // but keep dev visibility into real bugs.
        if (__DEV__) console.warn('[useRecommendations] fetch_failed', err?.response?.status, err?.message);
      });
  }, []);

  useEffect(() => {
    if (!user?.id) {
      requestIdRef.current += 1; // invalidate any in-flight request
      setRecommendations([]);
      return;
    }
    load(user.id);
  }, [user?.id, load]);

  return recommendations;
}
