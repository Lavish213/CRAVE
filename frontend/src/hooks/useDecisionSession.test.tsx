import React from 'react';
import { renderHook, waitFor } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fetchDecisionSession } from '../api/decisionSession';
import { useCityStore } from '../stores/cityStore';
import { useDecisionSession } from './useDecisionSession';

jest.mock('../api/decisionSession', () => ({
  fetchDecisionSession: jest.fn(),
}));
jest.mock('./useLocation', () => ({
  useLocation: jest.fn(() => ({ lat: 37.7, lng: -122.4 })),
}));

const mockedFetch = fetchDecisionSession as jest.MockedFunction<typeof fetchDecisionSession>;

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe('useDecisionSession', () => {
  beforeEach(() => {
    mockedFetch.mockReset();
    useCityStore.setState({
      selectedCity: {
        id: 'city-sf',
        name: 'San Francisco',
        slug: 'san-francisco',
        lat: 37.7749,
        lng: -122.4194,
      },
    });
  });

  it('uses the selected city instead of GPS and exposes the returned cards', async () => {
    mockedFetch.mockResolvedValue({ cards: [], degraded: false });

    const { result } = renderHook(() => useDecisionSession(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockedFetch).toHaveBeenCalledWith({
      city_id: 'city-sf',
      radius_miles: 20,
    });
    expect(result.current.data).toEqual({ cards: [], degraded: false });
  });
});
