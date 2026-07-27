// src/hooks/useTrending.ts
import { useCallback, useEffect, useState } from 'react';
import { PlaceOut, fetchTrending } from '../api/places';
import { useCityStore } from '../stores/cityStore';

// module-level cache: city_id → places (persists for app session)
const cache: Record<string, PlaceOut[]> = {};

export function useTrending(): PlaceOut[] {
  const [trending] = useTrendingWithRefresh();
  return trending;
}

// Same data as useTrending(), plus a refreshing flag and a refresh()
// function that bypasses the module-level cache — needed to support
// pull-to-refresh (search.tsx shows this list when no search is active).
export function useTrendingWithRefresh(): [PlaceOut[], boolean, () => void] {
  const selectedCity = useCityStore((s) => s.selectedCity);
  const [trending, setTrending] = useState<PlaceOut[]>(
    selectedCity ? (cache[selectedCity.id] ?? []) : []
  );
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback((cityId: string, { bypassCache }: { bypassCache: boolean }) => {
    if (!bypassCache && cache[cityId]) {
      setTrending(cache[cityId]);
      return;
    }
    setRefreshing(true);
    fetchTrending(cityId)
      .then((data) => {
        cache[cityId] = data;
        setTrending(data);
      })
      .catch((err) => {
        // Trending is non-critical — fail silently for the user (no error
        // UI for a nice-to-have row), but previously this swallowed the
        // error completely, including real bugs, with zero visibility.
        if (__DEV__) console.warn('[useTrending] fetchTrending_failed', err?.response?.status, err?.message);
      })
      .finally(() => setRefreshing(false));
  }, []);

  useEffect(() => {
    if (!selectedCity) return;
    load(selectedCity.id, { bypassCache: false });
  }, [selectedCity?.id, load]);

  const refresh = useCallback(() => {
    if (!selectedCity) return;
    load(selectedCity.id, { bypassCache: true });
  }, [selectedCity, load]);

  return [trending, refreshing, refresh];
}
