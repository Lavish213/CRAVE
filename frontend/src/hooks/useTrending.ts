// src/hooks/useTrending.ts
import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { PlaceOut, fetchTrending } from '../api/places';
import { useCityStore } from '../stores/cityStore';

// Mirrors trending.py's own TRENDING_CACHE_TTL (5 min) -- the backend
// response itself doesn't recompute more often than that, so caching it
// client-side for any longer just serves a staler answer than the
// backend would already give a fresh request, and any shorter just adds
// pointless refetches of an unchanged response. Previously a hand-rolled
// module-level cache with no TTL at all (persisted for the entire app
// session until an explicit pull-to-refresh), the one list-backed hook in
// the app not on React Query like every sibling screen (search/
// leaderboard/friends-feed).
const TRENDING_STALE_TIME = 5 * 60 * 1000;

export function useTrending(): PlaceOut[] {
  const [trending] = useTrendingWithRefresh();
  return trending;
}

// Same data as useTrending(), plus a refreshing flag and a refresh()
// function that bypasses the cache — needed to support pull-to-refresh
// (search.tsx shows this list when no search is active).
export function useTrendingWithRefresh(): [PlaceOut[], boolean, () => void] {
  const selectedCity = useCityStore((s) => s.selectedCity);

  const { data, isRefetching, refetch, error } = useQuery({
    queryKey: ['trending', selectedCity?.id],
    queryFn: () => fetchTrending(selectedCity!.id),
    enabled: !!selectedCity,
    staleTime: TRENDING_STALE_TIME,
  });

  // Trending is non-critical -- fail silently for the user (no error UI
  // for a nice-to-have row), but keep dev-only visibility into real bugs,
  // same as this hook's own pre-React-Query behavior.
  useEffect(() => {
    if (__DEV__ && error) {
      console.warn('[useTrending] fetchTrending_failed', (error as any)?.response?.status, (error as any)?.message);
    }
  }, [error]);

  const refresh = () => {
    refetch();
  };

  return [data ?? [], isRefetching, refresh];
}
