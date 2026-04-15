// src/hooks/useTrending.ts
import { useEffect, useState } from 'react';
import { PlaceOut, fetchTrending } from '../api/places';
import { useCityStore } from '../stores/cityStore';

// module-level cache: city_id → places (persists for app session)
const cache: Record<string, PlaceOut[]> = {};

export function useTrending(): PlaceOut[] {
  const selectedCity = useCityStore((s) => s.selectedCity);
  const [trending, setTrending] = useState<PlaceOut[]>(
    selectedCity ? (cache[selectedCity.id] ?? []) : []
  );

  useEffect(() => {
    if (!selectedCity) return;
    if (cache[selectedCity.id]) {
      setTrending(cache[selectedCity.id]);
      return;
    }
    fetchTrending(selectedCity.id)
      .then((data) => {
        cache[selectedCity.id] = data;
        setTrending(data);
      })
      .catch(() => {}); // trending is non-critical — fail silently
  }, [selectedCity?.id]);

  return trending;
}
