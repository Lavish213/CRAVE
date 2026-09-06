// Feed screen (app/(tabs)/index.tsx) — dedicated coverage for tier
// bucketing, viewability-based Recommendation Ledger exposure, click/save
// behavior, filtering, errors, and pagination de-duplication.
import React from 'react';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { FlashList } from '@shopify/flash-list';
import FeedScreen from '../app/(tabs)/index';
import { fetchPlaces, PlaceOut, PlacesResponse } from '../src/api/places';
import { fetchCities } from '../src/api/cities';
import { useCityStore } from '../src/stores/cityStore';
import { useAuthStore } from '../src/stores/authStore';
import { logRecommendationEvent, logRecommendationEvents } from '../src/utils/recommendationEventQueue';
import { DecisionSessionCard } from '../src/api/decisionSession';
import { useDecisionSession } from '../src/hooks/useDecisionSession';

const mockPush = jest.fn();
jest.mock('expo-router', () => ({
  useRouter: () => ({ push: mockPush }),
}));
jest.mock('../src/api/places', () => ({
  fetchPlaces: jest.fn(),
}));
jest.mock('../src/api/cities', () => ({
  fetchCities: jest.fn(),
}));
jest.mock('../src/hooks/useLocation', () => ({
  useLocation: () => null,
}));
jest.mock('../src/hooks/useTrending', () => ({
  useTrending: () => [],
}));
jest.mock('../src/hooks/useRecommendations', () => ({
  useRecommendations: () => [],
}));
jest.mock('../src/hooks/useDecisionSession', () => ({
  useDecisionSession: jest.fn(),
}));
jest.mock('../src/hooks/usePrefetchPlace', () => ({
  usePrefetchPlace: () => jest.fn(),
}));
jest.mock('../src/stores/authStore', () => ({
  useAuthStore: jest.fn(),
}));
const mockAddSave = jest.fn().mockResolvedValue(null);
const mockRemoveSave = jest.fn().mockResolvedValue(null);
const mockIsSaved = jest.fn().mockReturnValue(false);
jest.mock('../src/stores/cravesStore', () => {
  const hook: any = () => ({
    addSave: mockAddSave,
    removeSave: mockRemoveSave,
    isSaved: mockIsSaved,
  });
  return { useCravesStore: hook };
});
jest.mock('../src/components/AuthSheet', () => {
  const { Text } = require('react-native');
  return {
    AuthSheet: ({ visible }: { visible: boolean }) =>
      visible ? <Text testID="auth-sheet-visible">auth</Text> : null,
  };
});
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

const mockedFetchPlaces = fetchPlaces as jest.MockedFunction<typeof fetchPlaces>;
const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;
const mockedLogOne = logRecommendationEvent as jest.Mock;
const mockedLogMany = logRecommendationEvents as jest.Mock;
const mockedUseDecisionSession = useDecisionSession as jest.Mock;

const SF_CITY = { id: 'city-sf', name: 'San Francisco', slug: 'san-francisco', lat: 37.7749, lng: -122.4194 };

function makePlace(id: string, rank_percentile: number, overrides: Partial<PlaceOut> = {}): PlaceOut {
  return {
    id, name: id, city_id: 'city-sf', rank_score: 0.3, tier: 'solid', rank_percentile,
    distance_miles: null, category: 'Italian', categories: ['Italian'], address: null,
    lat: null, lng: null, image: null, primary_image_url: null, images: [],
    website: null, grubhub_url: null, has_menu: false, price_tier: 2,
    ...overrides,
  } as PlaceOut;
}

function page(items: PlaceOut[], total?: number, pageNum = 1, nextCursor: string | null = null): PlacesResponse {
  return { total: total ?? items.length, page: pageNum, page_size: 40, items, next_cursor: nextCursor };
}

function decisionCard(
  role: DecisionSessionCard['role'],
  id: string,
  reason_codes: DecisionSessionCard['reason_codes'],
): DecisionSessionCard {
  return { role, place: makePlace(id, 0.9), reason_codes };
}

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <FeedScreen />
    </QueryClientProvider>,
  );
}

describe('FeedScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedFetchPlaces.mockReset();
    (fetchCities as jest.Mock).mockReset().mockResolvedValue([]);
    mockAddSave.mockResolvedValue(null);
    mockRemoveSave.mockResolvedValue(null);
    mockIsSaved.mockReturnValue(false);
    useCityStore.setState({ selectedCity: SF_CITY, cities: [SF_CITY] });
    mockedUseAuthStore.mockImplementation((selector: (s: { user: unknown }) => unknown) =>
      selector({ user: null }),
    );
    mockedUseDecisionSession.mockReturnValue({
      data: { cards: [], degraded: false },
      isLoading: false,
      isError: false,
    });
  });

  it.each([0, 1, 2, 3])('renders exactly %i decision cards without padding thin sessions', async (count) => {
    const cards = [
      decisionCard('best_fit', 'decision-best', ['top_ranked_in_area']),
      decisionCard('safe_bet', 'decision-safe', ['high_percentile']),
      decisionCard('wildcard', 'decision-wild', ['different_cuisine']),
    ].slice(0, count);
    mockedUseDecisionSession.mockReturnValue({
      data: { cards, degraded: count < 3 },
      isLoading: false,
      isError: false,
    });
    mockedFetchPlaces.mockResolvedValue(page([makePlace('feed-place', 0.5)]));

    const { findByLabelText, queryByText, queryAllByText } = renderScreen();
    await findByLabelText(/^feed-place,/);

    if (count === 0) {
      expect(queryByText('DECIDE NOW')).toBeNull();
    } else {
      expect(queryByText('DECIDE NOW')).toBeTruthy();
    }
    expect(queryAllByText(/^(Best fit|Safe bet|Wildcard)$/)).toHaveLength(count);
  });

  it('logs decision impressions with role and position, then logs click before navigating', async () => {
    mockedUseDecisionSession.mockReturnValue({
      data: {
        cards: [
          decisionCard('best_fit', 'decision-best', ['top_ranked_in_area']),
          decisionCard('wildcard', 'decision-wild', ['different_cuisine']),
        ],
        degraded: true,
      },
      isLoading: false,
      isError: false,
    });
    mockedFetchPlaces.mockResolvedValue(page([makePlace('feed-place', 0.5)]));

    const { findByLabelText } = renderScreen();
    const wildcard = await findByLabelText(/^decision-wild,/);
    await waitFor(() => {
      const exposureBatch = mockedLogMany.mock.calls.flatMap((call) => call[0]);
      expect(exposureBatch).toEqual(expect.arrayContaining([
        expect.objectContaining({
          surface: 'decision_session', event_type: 'impression', place_id: 'decision-best',
          decision_role: 'best_fit', position: 0, rank_percentile: 0.9,
        }),
        expect.objectContaining({
          surface: 'decision_session', event_type: 'impression', place_id: 'decision-wild',
          decision_role: 'wildcard', position: 1, rank_percentile: 0.9,
        }),
        // All rows use the same FlashList viewability contract. If the first
        // normal Feed card is visible in the same callback it belongs in the
        // same exposure batch rather than being artificially split by source.
        expect.objectContaining({
          surface: 'feed', event_type: 'impression', place_id: 'feed-place', position: 0,
        }),
      ]));
    });

    fireEvent.press(wildcard);

    expect(mockedLogOne).toHaveBeenCalledWith(expect.objectContaining({
      surface: 'decision_session', event_type: 'click', place_id: 'decision-wild',
      decision_role: 'wildcard', position: 1, rank_percentile: 0.9,
    }));
    expect(mockPush).toHaveBeenCalledWith('/place/decision-wild');
  });

  it('buckets places into their tier sections and only renders sections that have places', async () => {
    const places = [
      makePlace('crave1', 0.97),
      makePlace('gem1', 0.85),
      makePlace('solid1', 0.5),
    ];
    mockedFetchPlaces.mockResolvedValue(page(places));

    const { findByText, queryByText } = renderScreen();

    expect(await findByText('CRAVE Picks')).toBeTruthy();
    expect(await findByText('Hidden Gems')).toBeTruthy();
    expect(await findByText('Worth Knowing')).toBeTruthy();
    expect(queryByText('Explore')).toBeNull();
  });

  it('logs one bounded impression batch for the first visible page, and does not re-log on an unrelated re-render', async () => {
    const places = [makePlace('p0', 0.97), makePlace('p1', 0.5)];
    mockedFetchPlaces.mockResolvedValue(page(places));

    const { getByLabelText } = renderScreen();
    await waitFor(() => expect(mockedLogMany).toHaveBeenCalledTimes(1));

    const batch = mockedLogMany.mock.calls[0][0];
    expect(batch).toEqual([
      expect.objectContaining({ surface: 'feed', event_type: 'impression', place_id: 'p0', position: 0, city_id: 'city-sf' }),
      expect.objectContaining({ surface: 'feed', event_type: 'impression', place_id: 'p1', position: 1, city_id: 'city-sf' }),
    ]);

    fireEvent.press(getByLabelText('Filter places'));
    expect(mockedLogMany).toHaveBeenCalledTimes(1);
  });

  it('logs a click event on card press with the real rank percentile, then navigates', async () => {
    const places = [makePlace('p0', 0.97)];
    mockedFetchPlaces.mockResolvedValue(page(places));

    const { findByLabelText } = renderScreen();
    const card = await findByLabelText(/^p0,/);
    fireEvent.press(card);

    expect(mockedLogOne).toHaveBeenCalledWith(
      expect.objectContaining({
        surface: 'feed', event_type: 'click', place_id: 'p0', rank_percentile: 0.97, city_id: 'city-sf',
      }),
    );
    expect(mockPush).toHaveBeenCalledWith('/place/p0');
  });

  it('opens AuthSheet on save when signed out, without calling addSave', async () => {
    mockedFetchPlaces.mockResolvedValue(page([makePlace('p0', 0.97)]));

    const { findByLabelText, findByTestId } = renderScreen();
    const saveBtn = await findByLabelText('Save p0');
    fireEvent.press(saveBtn);

    expect(mockAddSave).not.toHaveBeenCalled();
    expect(await findByTestId('auth-sheet-visible')).toBeTruthy();
  });

  it('calls addSave when signed in and unsaved, and removeSave when already saved', async () => {
    mockedUseAuthStore.mockImplementation((selector: (s: { user: unknown }) => unknown) =>
      selector({ user: { id: 'user-1' } }),
    );
    mockedFetchPlaces.mockResolvedValue(page([makePlace('p0', 0.97)]));

    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const buildTree = () => (
      <QueryClientProvider client={client}>
        <FeedScreen />
      </QueryClientProvider>
    );
    const { findByLabelText, rerender } = render(buildTree());
    const saveBtn = await findByLabelText('Save p0');
    await act(async () => {
      fireEvent.press(saveBtn);
    });
    expect(mockAddSave).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'p0' }),
      'user-1',
      expect.objectContaining({ surface: 'feed', rank_percentile: 0.97, city_id: 'city-sf' }),
    );

    mockIsSaved.mockReturnValue(true);
    rerender(buildTree());
    const removeBtn = await findByLabelText('Remove p0 from saves');
    await act(async () => {
      fireEvent.press(removeBtn);
    });
    expect(mockRemoveSave).toHaveBeenCalledWith('p0', 'user-1', expect.objectContaining({ surface: 'feed' }));
  });

  it('narrows rendered places by category filter without re-logging impressions', async () => {
    const places = [
      makePlace('p0', 0.97, { categories: ['Italian'], price_tier: 2 }),
      makePlace('p1', 0.85, { categories: ['Thai'], price_tier: 1 }),
    ];
    mockedFetchPlaces.mockResolvedValue(page(places));

    const { getByLabelText, queryByLabelText, findByLabelText } = renderScreen();
    await findByLabelText(/^p0,/);
    await waitFor(() => expect(mockedLogMany).toHaveBeenCalledTimes(1));

    fireEvent.press(getByLabelText('Filter places'));
    fireEvent.press(getByLabelText('Thai'));

    await waitFor(() => expect(queryByLabelText(/^p0,/)).toBeNull());
    expect(getByLabelText(/^p1,/)).toBeTruthy();
    expect(mockedLogMany).toHaveBeenCalledTimes(1);
  });

  it('shows the error state and lets retry re-fetch', async () => {
    mockedFetchPlaces.mockRejectedValueOnce(new Error('network'));
    mockedFetchPlaces.mockResolvedValueOnce(page([makePlace('p0', 0.97)]));

    const { findByText, findByLabelText } = renderScreen();
    expect(await findByText("Couldn't load places")).toBeTruthy();

    fireEvent.press(await findByText('Try again'));
    expect(await findByLabelText(/^p0,/)).toBeTruthy();
  });

  it('de-duplicates a place id that reappears across page fetches (the pagination-shift regression)', async () => {
    mockedFetchPlaces
      .mockResolvedValueOnce(page([makePlace('p0', 0.97), makePlace('p1', 0.5)], 3, 1, 'snapshot.2'))
      .mockResolvedValueOnce(page([makePlace('p1', 0.5), makePlace('p2', 0.3)], 3, 2));

    const { findByLabelText, queryAllByLabelText, UNSAFE_getByType } = renderScreen();
    await findByLabelText(/^p0,/);

    await act(async () => {
      UNSAFE_getByType(FlashList).props.onEndReached();
    });

    await findByLabelText(/^p2,/);
    expect(queryAllByLabelText(/^p1,/)).toHaveLength(1);
    expect(mockedFetchPlaces).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ pagination: 'cursor', cursor: 'snapshot.2' }),
    );
  });
});
