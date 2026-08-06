// src/hooks/useTrending.ts
import { useCallback, useEffect, useRef, useState } from 'react';
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

  // Tracks the most recently *started* request by sequence number, not just
  // cityId — two overlapping requests for the *same* city (e.g. refresh()
  // fired twice quickly, or a cache-bypass racing a plain load) both pass a
  // cityId-only check, so a slower of two same-city responses could still
  // overwrite a newer one and leave `refreshing` clobbered. Incremented for
  // both the cached and network paths.
  const latestRequestRef = useRef(0);

  const load = useCallback((cityId: string, { bypassCache }: { bypassCache: boolean }) => {
    const requestId = ++latestRequestRef.current;
    if (!bypassCache && cache[cityId]) {
      setTrending(cache[cityId]);
      setRefreshing(false);
      return;
    }
    setRefreshing(true);
    fetchTrending(cityId)
      .then((data) => {
        // Cache write stays unconditional — still correct data for a future
        // switch back to this city, even if it's not the one showing now.
        cache[cityId] = data;
        if (requestId !== latestRequestRef.current) return;
        setTrending(data);
      })
      .catch((err) => {
        // Trending is non-critical — fail silently for the user (no error
        // UI for a nice-to-have row), but previously this swallowed the
        // error completely, including real bugs, with zero visibility.
        if (__DEV__) console.warn('[useTrending] fetchTrending_failed', err?.response?.status, err?.message);
      })
      .finally(() => {
        if (requestId !== latestRequestRef.current) return;
        setRefreshing(false);
      });
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
