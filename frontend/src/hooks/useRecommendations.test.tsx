import { renderHook, waitFor } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React, { PropsWithChildren } from 'react';
import { fetchRecommendations, PlaceOut } from '../api/places';
import { useAuthStore } from '../stores/authStore';
import { useRecommendations } from './useRecommendations';

jest.mock('../api/places', () => ({ fetchRecommendations: jest.fn() }));
jest.mock('../stores/authStore', () => ({ useAuthStore: jest.fn() }));

const mockedFetchRecommendations = fetchRecommendations as jest.MockedFunction<typeof fetchRecommendations>;
const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;

const PLACE = { id: 'place-1', name: 'Recommended Place' } as unknown as PlaceOut;

function setUser(user: { id: string } | null): void {
  mockedUseAuthStore.mockImplementation((selector: (state: { user: { id: string } | null }) => unknown) =>
    selector({ user }),
  );
}

function createWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe('useRecommendations', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setUser({ id: 'user-1' });
    mockedFetchRecommendations.mockResolvedValue([PLACE]);
  });

  it('loads recommendations for an authenticated enabled consumer', async () => {
    const { result } = renderHook(() => useRecommendations(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.data).toEqual([PLACE]));
    expect(mockedFetchRecommendations).toHaveBeenCalledTimes(1);
    expect(mockedFetchRecommendations).toHaveBeenCalledWith(20, expect.any(AbortSignal));
  });

  it('does no hidden network work when the consumer is disabled', async () => {
    const { result } = renderHook(() => useRecommendations(false), { wrapper: createWrapper() });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(result.current.data).toBeUndefined();
    expect(mockedFetchRecommendations).not.toHaveBeenCalled();
  });

  it('does not fetch while signed out', async () => {
    setUser(null);
    const { result } = renderHook(() => useRecommendations(), { wrapper: createWrapper() });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(result.current.data).toBeUndefined();
    expect(mockedFetchRecommendations).not.toHaveBeenCalled();
  });

  it('invalidates an in-flight response when disabled before it resolves', async () => {
    let resolveRequest: (places: PlaceOut[]) => void = () => {};
    mockedFetchRecommendations.mockImplementationOnce(
      () => new Promise((resolve) => { resolveRequest = resolve; }),
    );

    const { result, rerender } = renderHook(
      ({ enabled }: { enabled: boolean }) => useRecommendations(enabled),
      { initialProps: { enabled: true }, wrapper: createWrapper() },
    );
    expect(mockedFetchRecommendations).toHaveBeenCalledTimes(1);

    rerender({ enabled: false });
    resolveRequest([PLACE]);
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(result.current.data).toBeUndefined();
  });

  it('does not reuse one account recommendation cache for another account', async () => {
    const wrapper = createWrapper();
    const { result, rerender } = renderHook(() => useRecommendations(), { wrapper });
    await waitFor(() => expect(result.current.data).toEqual([PLACE]));

    setUser({ id: 'user-2' });
    mockedFetchRecommendations.mockResolvedValueOnce([{ ...PLACE, id: 'place-2' }]);
    rerender({});

    await waitFor(() => expect(result.current.data?.[0]?.id).toBe('place-2'));
    expect(mockedFetchRecommendations).toHaveBeenCalledTimes(2);
  });
});
