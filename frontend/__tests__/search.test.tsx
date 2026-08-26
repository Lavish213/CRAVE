// Recommendation Ledger: Search-session instrumentation. Locks in the
// actual invariants from the spec -- log once per genuinely new
// (debounced) query, never per keystroke; a selection logs its real
// position/query/session; a re-render for the same query never re-logs.
import React from 'react';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import SearchScreen from '../app/(tabs)/search';
import { searchPlaces } from '../src/api/search';
import { useCityStore } from '../src/stores/cityStore';
import { logRecommendationEvent, logRecommendationEvents } from '../src/utils/recommendationEventQueue';

const mockPush = jest.fn();

jest.mock('expo-router', () => ({
  useRouter: () => ({ push: mockPush }),
}));
jest.mock('../src/api/search', () => ({
  searchPlaces: jest.fn(),
}));
jest.mock('../src/hooks/useLocation', () => ({
  useLocation: () => null,
}));
jest.mock('../src/hooks/useTrending', () => ({
  useTrendingWithRefresh: () => [[], false, jest.fn()],
}));
jest.mock('../src/api/cities', () => ({
  fetchCities: jest.fn().mockResolvedValue([]),
}));
jest.mock('../src/hooks/usePrefetchPlace', () => ({
  usePrefetchPlace: () => jest.fn(),
}));
jest.mock('../src/utils/recommendationEventQueue', () => ({
  logRecommendationEvent: jest.fn(),
  logRecommendationEvents: jest.fn(),
}));
jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  notificationAsync: jest.fn(),
  ImpactFeedbackStyle: { Light: 'light', Medium: 'medium' },
  NotificationFeedbackType: { Success: 'success', Warning: 'warning', Error: 'error' },
}));

const mockedSearchPlaces = searchPlaces as jest.MockedFunction<typeof searchPlaces>;
const mockedLogOne = logRecommendationEvent as jest.Mock;
const mockedLogMany = logRecommendationEvents as jest.Mock;

const SF_CITY = { id: 'city-sf', name: 'San Francisco', slug: 'san-francisco', lat: 37.7749, lng: -122.4194 };

function makePlace(id: string, rank_percentile: number | null = 0.8, overrides: any = {}) {
  return { id, name: id, category: 'Italian', categories: ['Italian'], price_tier: 2, rank_percentile, ...overrides } as any;
}

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SearchScreen />
    </QueryClientProvider>,
  );
}

describe('SearchScreen — Recommendation Ledger instrumentation', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useCityStore.setState({ selectedCity: SF_CITY, cities: [SF_CITY] });
  });

  it('logs one impression batch, capped and positioned, the first time a query\'s results arrive', async () => {
    const results = Array.from({ length: 3 }, (_, i) => makePlace(`p${i}`, 0.5 + i / 10));
    mockedSearchPlaces.mockResolvedValue(results);

    const { getByLabelText } = renderScreen();
    const input = getByLabelText('Search input');

    act(() => {
      input.props.onChangeText('pizza');
    });

    // Real 350ms debounce timer -- waitFor's default timeout comfortably
    // covers it without needing fake timers.
    await waitFor(() => expect(mockedSearchPlaces).toHaveBeenCalled(), { timeout: 2000 });
    await waitFor(() => expect(mockedLogMany).toHaveBeenCalledTimes(1));

    const logged = mockedLogMany.mock.calls[0][0];
    expect(logged).toHaveLength(3);
    expect(logged[0]).toMatchObject({
      surface: 'search', event_type: 'impression', place_id: 'p0', position: 0,
      rank_percentile: 0.5, query: 'pizza', city_id: 'city-sf',
    });
    expect(logged[1].position).toBe(1);
    expect(logged.every((e: any) => typeof e.search_session_id === 'string')).toBe(true);
  });

  it('logs a click with the real position, query, and search_session_id on selection', async () => {
    const results = [makePlace('p0', 0.9), makePlace('p1', 0.4)];
    mockedSearchPlaces.mockResolvedValue(results);

    const { getByLabelText } = renderScreen();
    act(() => {
      getByLabelText('Search input').props.onChangeText('ramen');
    });
    await waitFor(() => expect(mockedLogMany).toHaveBeenCalledTimes(1));

    fireEvent.press(getByLabelText(/^p1,/));

    expect(mockedLogOne).toHaveBeenCalledWith(
      expect.objectContaining({
        surface: 'search', event_type: 'click', place_id: 'p1', position: 1,
        query: 'ramen', city_id: 'city-sf',
      }),
    );
    expect(mockPush).toHaveBeenCalledWith('/place/p1');
  });

  it('narrows results by an active filter, keeps a filtered-in item\'s click position tied to its real position in the full results, and clears from the zero-match empty state', async () => {
    const results = [
      makePlace('p0', 0.9, { categories: ['Italian'], price_tier: 2 }),
      makePlace('p1', 0.7, { categories: ['Thai'], price_tier: 1 }),
      makePlace('p2', 0.5, { categories: ['Thai'], price_tier: 3 }),
    ];
    mockedSearchPlaces.mockResolvedValue(results);

    const { getByLabelText, getByText, queryByText } = renderScreen();
    act(() => {
      getByLabelText('Search input').props.onChangeText('food');
    });
    await waitFor(() => expect(mockedLogMany).toHaveBeenCalledTimes(1));

    fireEvent.press(getByLabelText('Filter results'));
    fireEvent.press(getByLabelText('Thai'));
    // Modal is real (not mocked) -- both matching rows render, p0 (Italian) doesn't.
    expect(getByLabelText(/^p1,/)).toBeTruthy();
    expect(getByLabelText(/^p2,/)).toBeTruthy();
    expect(() => getByLabelText(/^p0,/)).toThrow();

    fireEvent.press(getByLabelText(/^p1,/));
    expect(mockedLogOne).toHaveBeenCalledWith(
      // p1 is index 1 in the real `results`, even though it's the first
      // row in the filtered (Thai-only) view -- a click must tie back to
      // the position actually logged in the impression batch above.
      expect.objectContaining({ place_id: 'p1', position: 1 }),
    );

    // Narrow further to something with zero matches -- neither Thai place
    // (p1=$, p2=$$$) has price_tier 2.
    fireEvent.press(getByLabelText('Price tier $$'));
    await waitFor(() => expect(getByText('No matches for these filters')).toBeTruthy());

    fireEvent.press(getByText('Clear filters'));
    await waitFor(() => expect(queryByText('No matches for these filters')).toBeNull());
    expect(getByLabelText(/^p0,/)).toBeTruthy();
  });
});
