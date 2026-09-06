import React from 'react';
import { renderHook, waitFor } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fetchTrending } from '../api/places';
import { useCityStore } from '../stores/cityStore';
import { useTrendingWithRefresh } from './useTrending';

jest.mock('../api/places', () => ({
  fetchTrending: jest.fn(),
}));

const mockedFetchTrending = fetchTrending as jest.MockedFunction<typeof fetchTrending>;

const SF_CITY = { id: 'city-sf', name: 'San Francisco', slug: 'san-francisco', lat: 37.7749, lng: -122.4194 };

function makePlace(id: string) {
  return { id, name: id } as any;
}

function makeWrapper(client: QueryClient) {
  return function wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe('useTrendingWithRefresh', () => {
  beforeEach(() => {
    mockedFetchTrending.mockReset();
    useCityStore.setState({ selectedCity: SF_CITY });
  });

  it('fetches trending places for the selected city', async () => {
    mockedFetchTrending.mockResolvedValue([makePlace('p0')]);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    const { result } = renderHook(() => useTrendingWithRefresh(), { wrapper: makeWrapper(client) });

    await waitFor(() => expect(result.current[0]).toEqual([makePlace('p0')]));
    expect(mockedFetchTrending).toHaveBeenCalledWith('city-sf');
  });

  it('does not fetch again for the same city within the stale window -- no more a per-session-forever cache, but not a refetch-on-every-mount either', async () => {
    mockedFetchTrending.mockResolvedValue([makePlace('p0')]);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    const { result, unmount } = renderHook(() => useTrendingWithRefresh(), { wrapper: makeWrapper(client) });
    await waitFor(() => expect(result.current[0]).toEqual([makePlace('p0')]));
    unmount();

    renderHook(() => useTrendingWithRefresh(), { wrapper: makeWrapper(client) });
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(mockedFetchTrending).toHaveBeenCalledTimes(1);
  });

  it('refresh() bypasses staleness and refetches immediately', async () => {
    mockedFetchTrending.mockResolvedValueOnce([makePlace('p0')]);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    const { result } = renderHook(() => useTrendingWithRefresh(), { wrapper: makeWrapper(client) });
    await waitFor(() => expect(result.current[0]).toEqual([makePlace('p0')]));

    mockedFetchTrending.mockResolvedValueOnce([makePlace('p1')]);
    result.current[2](); // refresh()

    await waitFor(() => expect(result.current[0]).toEqual([makePlace('p1')]));
    expect(mockedFetchTrending).toHaveBeenCalledTimes(2);
  });

  it('fails silently -- no thrown error, just an empty list', async () => {
    mockedFetchTrending.mockRejectedValue(new Error('network'));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    const { result } = renderHook(() => useTrendingWithRefresh(), { wrapper: makeWrapper(client) });

    // result.current[1] is isRefetching, which is already false during
    // the *initial* fetch (isRefetching only ever describes a refetch of
    // already-settled data) -- asserting on it alone could pass before
    // the rejection has actually settled. Wait on the query's own state
    // instead, so this genuinely covers the post-rejection case.
    await waitFor(() => expect(client.getQueryState(['trending', 'city-sf'])?.status).toBe('error'));
    expect(result.current[1]).toBe(false);
    expect(result.current[0]).toEqual([]);
  });

  it('does not fetch at all when no city is selected', () => {
    useCityStore.setState({ selectedCity: null });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    renderHook(() => useTrendingWithRefresh(), { wrapper: makeWrapper(client) });

    expect(mockedFetchTrending).not.toHaveBeenCalled();
  });

  it('refresh() is a no-op when no city is selected, rather than crashing into an error state', () => {
    useCityStore.setState({ selectedCity: null });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    const { result } = renderHook(() => useTrendingWithRefresh(), { wrapper: makeWrapper(client) });
    result.current[2](); // refresh()

    expect(mockedFetchTrending).not.toHaveBeenCalled();
  });
});
