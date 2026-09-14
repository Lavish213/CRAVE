// Real gap this closes: usePrefetchPlace warmed the cache under a
// hand-rolled ['place', placeId] key that place/[id].tsx's own useQuery
// never read from (it uses foundationQueryKey({ scope: 'place',
// entity: 'detail', params: { id } })) -- every prefetch-on-tap was a
// wasted network request the destination screen threw away and re-fetched
// under its own key. This locks the two keys together.
import React from 'react';
import { renderHook, waitFor } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { usePrefetchPlace } from './usePrefetchPlace';
import { fetchPlaceDetail } from '../api/places';
import { foundationQueryKey } from '../contracts/foundationGate';

jest.mock('../api/places', () => ({
  fetchPlaceDetail: jest.fn(),
}));

const mockedFetchPlaceDetail = fetchPlaceDetail as jest.MockedFunction<typeof fetchPlaceDetail>;

function makeWrapper(client: QueryClient) {
  return function wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe('usePrefetchPlace', () => {
  beforeEach(() => {
    mockedFetchPlaceDetail.mockReset();
  });

  it('prefetches under the exact same cache key place/[id].tsx reads from', async () => {
    mockedFetchPlaceDetail.mockResolvedValue({ id: 'place-1', name: 'Tasty Spot' } as any);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => usePrefetchPlace(), { wrapper: makeWrapper(client) });

    result.current('place-1');
    await waitFor(() => expect(mockedFetchPlaceDetail).toHaveBeenCalledWith('place-1'));

    const realScreenKey = foundationQueryKey({ scope: 'place', entity: 'detail', params: { id: 'place-1' } });
    await waitFor(() => expect(client.getQueryData(realScreenKey)).toEqual({ id: 'place-1', name: 'Tasty Spot' }));
  });

  it('a real screen reading the same key sees the prefetched data without refetching', async () => {
    mockedFetchPlaceDetail.mockResolvedValue({ id: 'place-2', name: 'Old Favorite' } as any);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => usePrefetchPlace(), { wrapper: makeWrapper(client) });

    result.current('place-2');
    await waitFor(() => expect(mockedFetchPlaceDetail).toHaveBeenCalledTimes(1));

    // Simulate the real screen's own useQuery reading the identical key --
    // it must find the just-warmed cache entry, not trigger a second fetch.
    const realScreenKey = foundationQueryKey({ scope: 'place', entity: 'detail', params: { id: 'place-2' } });
    expect(client.getQueryData(realScreenKey)).toEqual({ id: 'place-2', name: 'Old Favorite' });
    expect(mockedFetchPlaceDetail).toHaveBeenCalledTimes(1);
  });

  it('invalidating the real screen key also invalidates whatever this hook prefetched', async () => {
    mockedFetchPlaceDetail.mockResolvedValue({ id: 'place-3', name: 'New Spot' } as any);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => usePrefetchPlace(), { wrapper: makeWrapper(client) });

    result.current('place-3');
    await waitFor(() => expect(mockedFetchPlaceDetail).toHaveBeenCalledTimes(1));

    const realScreenKey = foundationQueryKey({ scope: 'place', entity: 'detail', params: { id: 'place-3' } });
    await client.invalidateQueries({ queryKey: realScreenKey });
    expect(client.getQueryState(realScreenKey)?.isInvalidated).toBe(true);
  });

  it('does nothing for a null/undefined placeId', () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => usePrefetchPlace(), { wrapper: makeWrapper(client) });

    result.current(null);
    result.current(undefined);
    expect(mockedFetchPlaceDetail).not.toHaveBeenCalled();
  });
});
