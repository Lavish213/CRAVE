import { useQueryClient } from '@tanstack/react-query';
import { fetchPlaceDetail } from '../api/places';
import { STALE_TIME, foundationQueryKey } from '../contracts/foundationGate';

/**
 * Warms the place-detail cache before navigation actually commits.
 *
 * No queryClient.prefetchQuery() call existed anywhere in the app --
 * every place-detail navigation paid its full round trip only after the
 * destination screen had already mounted. Call the returned function from
 * a card's onPressIn (fires before onPress, which is what actually
 * navigates), so by the time place/[id].tsx mounts and runs its own
 * identical useQuery, the data is often already sitting in cache instead
 * of triggering a second, redundant fetch.
 *
 * The queryKey here must exactly match place/[id].tsx's own
 * foundationQueryKey({ scope: 'place', entity: 'detail', params: { id } })
 * -- it previously used a hand-rolled ['place', placeId] key instead, a
 * different cache entry the real screen's useQuery never read from. That
 * silently turned every prefetch-on-tap into a wasted network request:
 * the destination screen always re-fetched under its own key, discarding
 * whatever this hook had just warmed.
 */
export function usePrefetchPlace() {
  const queryClient = useQueryClient();

  return (placeId: string | null | undefined) => {
    if (!placeId) return;
    queryClient.prefetchQuery({
      queryKey: foundationQueryKey({ scope: 'place', entity: 'detail', params: { id: placeId } }),
      queryFn: () => fetchPlaceDetail(placeId),
      staleTime: STALE_TIME.normal,
    });
  };
}
