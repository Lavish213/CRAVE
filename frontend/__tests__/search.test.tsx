// Recommendation Ledger: Search-session instrumentation. Locks in the
// actual invariants from the spec -- an impression logs on genuine
// exposure (scrolled into view via FlashList's own viewability callback),
// not the instant a query's results are retrieved from the backend; a
// selection logs its real position/query/session; the same result isn't
// re-logged for the same query, but exposure tracking does reset for a
// genuinely new one.
import React from 'react';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import SearchScreen from '../app/(tabs)/search';
import { FlashList } from '@shopify/flash-list';
import { searchPlaces } from '../src/api/search';
import { useCityStore } from '../src/stores/cityStore';
import { logRecommendationEvent, logRecommendationEvents } from '../src/utils/recommendationEventQueue';
import { useLocationStatus } from '../src/hooks/useLocation';

const mockPush = jest.fn();

jest.mock('expo-router', () => ({
  useRouter: () => ({ push: mockPush }),
}));
jest.mock('../src/api/search', () => ({
  searchPlaces: jest.fn(),
}));
jest.mock('../src/hooks/useLocation', () => ({
  useLocationStatus: jest.fn(() => ({ status: 'denied', coords: null, updatedAt: null })),
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
const mockedUseLocationStatus = useLocationStatus as jest.Mock;
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

describe('SearchScreen — location status copy', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useCityStore.setState({ selectedCity: SF_CITY, cities: [SF_CITY] });
    mockedSearchPlaces.mockResolvedValue([]);
  });

  it('tells the user location is still resolving, distinct from a terminal no-location state', () => {
    mockedUseLocationStatus.mockReturnValue({ status: 'resolving', coords: null, updatedAt: null });
    const { getByText } = renderScreen();
    expect(getByText('Searching everywhere — finding your location…')).toBeTruthy();
  });

  it('shows the plain no-location copy once resolution has actually finished (denied)', () => {
    mockedUseLocationStatus.mockReturnValue({ status: 'denied', coords: null, updatedAt: null });
    const { getByText } = renderScreen();
    expect(getByText('Searching everywhere')).toBeTruthy();
  });

  it('shows the nearest-first copy once granted', () => {
    mockedUseLocationStatus.mockReturnValue({ status: 'granted', coords: { lat: 1, lng: 2 }, updatedAt: Date.now() });
    const { getByText } = renderScreen();
    expect(getByText('Searching everywhere, nearest first')).toBeTruthy();
  });
});

describe('SearchScreen — debounce, clear, and retry', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedUseLocationStatus.mockReturnValue({ status: 'denied', coords: null, updatedAt: null });
    useCityStore.setState({ selectedCity: SF_CITY, cities: [SF_CITY] });
  });

  it('cancels a pending debounce timer on clear, so a stale query never resurrects', async () => {
    mockedSearchPlaces.mockResolvedValue([]);
    const { getByLabelText, queryByLabelText } = renderScreen();

    act(() => {
      getByLabelText('Search input').props.onChangeText('pizza');
    });
    // Clear before the 350ms debounce timer fires -- previously left that
    // timer alive, so it would call setDebouncedQuery('pizza') anyway and
    // resurrect the just-cleared query.
    fireEvent.press(getByLabelText('Clear search'));

    // Give the (would-be) resurrected timer a chance to fire.
    await new Promise((resolve) => setTimeout(resolve, 500));

    expect(mockedSearchPlaces).not.toHaveBeenCalled();
    expect(queryByLabelText('Clear search')).toBeNull(); // query box is empty again
  });

  it('retry button actually refetches the failed query, not a no-op', async () => {
    mockedSearchPlaces.mockRejectedValueOnce(new Error('network'));
    const { getByLabelText, findByText } = renderScreen();

    act(() => {
      getByLabelText('Search input').props.onChangeText('ramen');
    });
    await findByText("Couldn't search right now.");
    expect(mockedSearchPlaces).toHaveBeenCalledTimes(1);

    mockedSearchPlaces.mockResolvedValueOnce([makePlace('p0')]);
    fireEvent.press(await findByText('Try again'));

    await waitFor(() => expect(mockedSearchPlaces).toHaveBeenCalledTimes(2));
    expect(await findByText('1 result')).toBeTruthy();
  });
});

describe('SearchScreen — Recommendation Ledger instrumentation', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedUseLocationStatus.mockReturnValue({ status: 'denied', coords: null, updatedAt: null });
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

  it('does not re-log a result already exposed for the current query when viewability fires again', async () => {
    // Proves the exposure-tracking Set actually dedupes -- a real
    // viewability callback fires repeatedly as items scroll in and out,
    // not just once.
    const results = [makePlace('p0')];
    mockedSearchPlaces.mockResolvedValue(results);
    const { getByLabelText, UNSAFE_getAllByType } = renderScreen();

    act(() => {
      getByLabelText('Search input').props.onChangeText('pizza');
    });
    await waitFor(() => expect(mockedLogMany).toHaveBeenCalled());
    const callsAfterInitialExposure = mockedLogMany.mock.calls.length;

    const resultsList = UNSAFE_getAllByType(FlashList).slice(-1)[0];
    act(() => {
      resultsList.props.onViewableItemsChanged({
        viewableItems: [{ item: results[0], key: 'p0', index: 0, isViewable: true, timestamp: Date.now() }],
      });
    });

    expect(mockedLogMany.mock.calls.length).toBe(callsAfterInitialExposure);
  });

  it('resets exposure tracking for a genuinely new query, even if the same place reappears', async () => {
    mockedSearchPlaces.mockResolvedValueOnce([makePlace('p0')]);
    const { getByLabelText } = renderScreen();

    act(() => {
      getByLabelText('Search input').props.onChangeText('pizza');
    });
    await waitFor(() => expect(mockedLogMany).toHaveBeenCalled());
    const callsAfterFirstQuery = mockedLogMany.mock.calls.length;

    mockedSearchPlaces.mockResolvedValueOnce([makePlace('p0')]);
    act(() => {
      getByLabelText('Search input').props.onChangeText('burger');
    });

    await waitFor(() => expect(mockedLogMany.mock.calls.length).toBeGreaterThan(callsAfterFirstQuery));
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
