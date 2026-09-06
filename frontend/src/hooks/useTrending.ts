// src/hooks/useTrending.ts
import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { PlaceOut, fetchTrending } from '../api/places';
import { useCityStore } from '../stores/cityStore';

const TRENDING_STALE_TIME = 5 * 60 * 1000;

/**
 * `enabled` lets a hidden/feature-flagged consumer keep hook ordering stable
 * without performing network work. Search uses the default `true`; Feed
 * passes its discovery-strip feature flag so a strip that is deliberately
 * not rendered does not keep fetching behind the scenes.
 */
export function useTrending(enabled = true): PlaceOut[] {
  const [trending] = useTrendingWithRefresh(enabled);
  return trending;
}

export function useTrendingWithRefresh(enabled = true): [PlaceOut[], boolean, () => void] {
  const selectedCity = useCityStore((s) => s.selectedCity);

  const { data, isRefetching, refetch, error } = useQuery({
    queryKey: ['trending', selectedCity?.id],
    queryFn: () => fetchTrending(selectedCity!.id),
    enabled: enabled && !!selectedCity,
    staleTime: TRENDING_STALE_TIME,
  });

  useEffect(() => {
    if (__DEV__ && error) {
      const status = typeof error === 'object' && error !== null && 'response' in error
        ? (error as { response?: { status?: number } }).response?.status
        : undefined;
      const message = error instanceof Error ? error.message : String(error);
      console.warn('[useTrending] fetchTrending_failed', status, message);
    }
  }, [error]);

  const refresh = () => {
    if (!enabled || !selectedCity) return;
    void refetch();
  };

  return [enabled ? (data ?? []) : [], enabled && isRefetching, refresh];
}
