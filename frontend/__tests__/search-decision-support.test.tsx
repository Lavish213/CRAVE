// Search Screen Contract §5/§6 (zero-state decision support) and §11
// (zero-result relaxation). Kept in its own file, separate from
// search.test.tsx's Recommendation Ledger/Reason Block/Wave 5 suites --
// real-timer-driven React Query + FlashList tests accumulating in one very
// large file made this sandbox's test runner intermittently corrupt an
// unrelated later test's render() call ("Can't access .root on unmounted
// test renderer"), reproducible even on pre-existing tests untouched by
// this change. Splitting isolates each file's module/render state.
import React from 'react';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import SearchScreen, { intentShortcutForHour, zeroResultInfo } from '../src/screens/SearchScreen';
import { searchPlaces } from '../src/api/search';
import { useCityStore } from '../src/stores/cityStore';
import { useRecentSearchesStore } from '../src/stores/recentSearchesStore';
import { useLocationStatus } from '../src/hooks/useLocation';

jest.mock('expo-router', () => ({
  useRouter: () => ({ push: jest.fn() }),
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
jest.mock('expo-crypto', () => ({
  randomUUID: jest.fn(() => 'test-search-session-id'),
}));

const mockedSearchPlaces = searchPlaces as jest.MockedFunction<typeof searchPlaces>;
const mockedUseLocationStatus = useLocationStatus as jest.Mock;

const SF_CITY = { id: 'city-sf', name: 'San Francisco', slug: 'san-francisco', lat: 37.7749, lng: -122.4194 };

function makeSearchResult(items: any[], overrides: Record<string, unknown> = {}) {
  return {
    total: items.length,
    page: 1,
    page_size: Math.max(1, items.length),
    items,
    interpretation: {
      original_query: 'query', lookup_query: 'query', price_tier: null,
      required_categories: [], hard_constraints: [],
      unsupported_hard_constraints: [], context: [], uncertain: false,
    },
    exact_match_id: null,
    relaxed_constraints: [],
    ...overrides,
  };
}

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SearchScreen />
    </QueryClientProvider>,
  );
}

describe('intentShortcutForHour (Search Screen Contract §5/§6)', () => {
  it('returns a real, non-empty phrase for every hour of the day', () => {
    for (let hour = 0; hour < 24; hour++) {
      expect(intentShortcutForHour(hour).length).toBeGreaterThan(0);
    }
  });

  it('picks a distinct phrase per time-of-day bucket', () => {
    expect(intentShortcutForHour(8)).toBe('Breakfast nearby');
    expect(intentShortcutForHour(12)).toBe('Quick lunch');
    expect(intentShortcutForHour(16)).toBe('Afternoon coffee');
    expect(intentShortcutForHour(19)).toBe('Dinner tonight');
    expect(intentShortcutForHour(23)).toBe('Late-night eats');
    expect(intentShortcutForHour(2)).toBe('Late-night eats');
  });
});

describe('zeroResultInfo (Search Screen Contract §11)', () => {
  const baseInterpretation = {
    original_query: 'q', lookup_query: 'q', price_tier: null,
    required_categories: [], hard_constraints: [],
    unsupported_hard_constraints: [], context: [], uncertain: false,
  };

  it('names the price filter as the relaxation when it is the only soft constraint and was not already relaxed', () => {
    const info = zeroResultInfo({ ...baseInterpretation, price_tier: 1 }, false);
    expect(info.body).toContain('$ price filter');
    expect(info.relaxKey).toBe('price');
  });

  it('names a soft context constraint (e.g. near_me) as the relaxation', () => {
    const info = zeroResultInfo({ ...baseInterpretation, context: ['near_me'] }, false);
    expect(info.body).toBe('No matches with near me.');
    expect(info.relaxKey).toBe('near_me');
  });

  it('never offers a dietary/allergy hard constraint as a relaxation, even if the interpreter also listed it under context', () => {
    const info = zeroResultInfo(
      { ...baseInterpretation, context: ['vegan'], hard_constraints: ['vegan'] },
      false,
    );
    expect(info.relaxKey).toBeUndefined();
  });

  it('does not re-suggest price once it has already been relaxed', () => {
    const info = zeroResultInfo({ ...baseInterpretation, price_tier: 1 }, true);
    expect(info.relaxKey).toBeUndefined();
    expect(info.body).toBe('Nothing matched "q" right now.');
  });

  it('states directly that nothing can be verified, without implying a broader search would help, for an unsupported hard constraint', () => {
    const info = zeroResultInfo(
      { ...baseInterpretation, unsupported_hard_constraints: ['nut_free'] },
      false,
    );
    expect(info.relaxKey).toBeUndefined();
    expect(info.body).not.toMatch(/broader|broaden/i);
    expect(info.body).toContain("can't verify");
  });

  it('names the actual query rather than a generic message when no safe relaxation exists', () => {
    const info = zeroResultInfo(baseInterpretation, false);
    expect(info.relaxKey).toBeUndefined();
    expect(info.body).toBe('Nothing matched "q" right now.');
    expect(info.body).not.toMatch(/broader|broaden/i);
  });
});

describe('SearchScreen — zero-state decision support (Search Screen Contract §5/§6)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useRecentSearchesStore.getState().clear();
    mockedUseLocationStatus.mockReturnValue({ status: 'denied', coords: null, updatedAt: null });
    useCityStore.setState({ selectedCity: SF_CITY, cities: [SF_CITY] });
  });

  it('shows a time-relevant intent shortcut and searches immediately on tap', async () => {
    // Resolves empty on purpose: these zero-state tests only need to prove
    // the shortcut triggers the right search call, not render a result
    // list -- avoids depending on FlashList's own async mount timing.
    mockedSearchPlaces.mockResolvedValue(makeSearchResult([]));
    const { findByText } = renderScreen();

    const expected = intentShortcutForHour(new Date().getHours());
    fireEvent.press(await findByText(expected));

    // Wait for the actual empty-result UI (not just the mock call) so the
    // query has genuinely resolved and settled before the test ends.
    await findByText('Nothing matched "query" right now.');
    expect(mockedSearchPlaces).toHaveBeenCalledWith(
      expect.objectContaining({ query: expected }),
      expect.anything(),
    );
  });

  it('shows recent searches only once one exists, and searching one again re-runs it', async () => {
    mockedSearchPlaces.mockResolvedValue(makeSearchResult([]));

    // Seed before mount, not after: a real "recent search" is always
    // already in the store by the time the zero-state renders.
    useRecentSearchesStore.getState().addQuery('late-night ramen near home');
    const { findByText } = renderScreen();

    fireEvent.press(await findByText('late-night ramen near home'));
    await findByText('Nothing matched "query" right now.');
    expect(mockedSearchPlaces).toHaveBeenCalledWith(
      expect.objectContaining({ query: 'late-night ramen near home' }),
      expect.anything(),
    );
  });

  it('shows no recent searches when none have been made yet', () => {
    const { queryByText } = renderScreen();
    expect(queryByText('RECENT SEARCHES')).toBeNull();
  });

  it('records an explicitly submitted query into recent searches', async () => {
    mockedSearchPlaces.mockResolvedValue(makeSearchResult([]));
    const { getByLabelText, findByText } = renderScreen();
    const input = getByLabelText('Search input');

    act(() => input.props.onChangeText('spicy noodles'));
    act(() => input.props.onSubmitEditing());

    await findByText('Nothing matched "query" right now.');
    expect(mockedSearchPlaces).toHaveBeenCalledWith(
      expect.objectContaining({ query: 'spicy noodles' }),
      expect.anything(),
    );
    expect(useRecentSearchesStore.getState().queries).toContain('spicy noodles');
  });

  it('offers a real city/location shortcut in the zero-state', () => {
    const { getByLabelText } = renderScreen();
    expect(getByLabelText('Use my location')).toBeTruthy();
  });
});

describe('SearchScreen — zero-result relaxation offer end to end (Search Screen Contract §11)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedUseLocationStatus.mockReturnValue({ status: 'denied', coords: null, updatedAt: null });
    useCityStore.setState({ selectedCity: SF_CITY, cities: [SF_CITY] });
  });

  it('names the specific constraint and removing it actually re-searches without it', async () => {
    // Both calls resolve empty on purpose -- this only needs to prove the
    // second API call actually dropped "near me" from the query, not that
    // a result list renders. The second response's interpretation
    // genuinely differs (no more near_me context) so its resulting text is
    // a real, distinguishable signal that the second call has settled.
    mockedSearchPlaces
      .mockResolvedValueOnce(makeSearchResult([], {
        total: 0,
        interpretation: {
          original_query: 'ramen near me', lookup_query: 'ramen', price_tier: null,
          required_categories: [], hard_constraints: [],
          unsupported_hard_constraints: [], context: ['near_me'], uncertain: false,
        },
      }))
      .mockResolvedValueOnce(makeSearchResult([], {
        total: 0,
        interpretation: {
          original_query: 'ramen', lookup_query: 'ramen', price_tier: null,
          required_categories: [], hard_constraints: [],
          unsupported_hard_constraints: [], context: [], uncertain: false,
        },
      }));

    const { getByLabelText, findByText } = renderScreen();
    act(() => getByLabelText('Search input').props.onChangeText('ramen near me'));

    expect(await findByText('No matches with near me.')).toBeTruthy();
    fireEvent.press(await findByText('Remove near me'));

    await findByText('Nothing matched "ramen" right now.');
    expect(mockedSearchPlaces).toHaveBeenCalledTimes(2);
    expect(mockedSearchPlaces.mock.calls[1][0].query).toBe('ramen');
  });
});
