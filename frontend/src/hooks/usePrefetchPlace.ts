import { useQueryClient } from '@tanstack/react-query';
import { fetchPlaceDetail } from '../api/places';

// Matches place/[id].tsx's own useQuery(['place', id]) staleTime exactly --
// if it didn't, prefetching here would still count as "fresh" for a
// different window than the screen itself uses, defeating the point.
const PLACE_DETAIL_STALE_TIME = 5 * 60 * 1000;

/**
 * Warms the place-detail cache before navigation actually commits.
 *
 * No queryClient.prefetchQuery() call existed anywhere in the app --
 * every place-detail navigation paid its full round trip only after the
 * destination screen had already mounted. Call the returned function from
 * a card's onPressIn (fires before onPress, which is what actually
 * navigates), so by the time place/[id].tsx mounts and runs its own
 * identical useQuery(['place', id]), the data is often already sitting in
 * cache instead of triggering a second, redundant fetch.
 */
export function usePrefetchPlace() {
  const queryClient = useQueryClient();

  return (placeId: string | null | undefined) => {
    if (!placeId) return;
    queryClient.prefetchQuery({
      queryKey: ['place', placeId],
      queryFn: () => fetchPlaceDetail(placeId),
      staleTime: PLACE_DETAIL_STALE_TIME,
    });
  };
}
