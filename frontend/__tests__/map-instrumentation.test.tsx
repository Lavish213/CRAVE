// Recommendation Ledger: Map-screen instrumentation, surface='map'.
// Deliberately narrow, per instruction: one bounded/positioned impression
// batch per settled fetch (not per pan/region callback -- the debounce +
// coverage-cache guards already suppress those); a single click event on
// the bottom-sheet's "open" tap (which already performs the place-detail
// navigation); no event at all for a bare pin tap (only reveals the
// preview sheet) or a cluster tap (no single place_id to log); no raw
// lat/lng ever appears in a logged event, only place_id/tier context.
import React from 'react';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';
import MapScreen from '../app/(tabs)/map';
import { fetchMapGeoJSON, fetchSavedPlacesGeoJSON } from '../src/api/map';
import { useCityStore } from '../src/stores/cityStore';
import { useAuthStore } from '../src/stores/authStore';
import { logRecommendationEvent, logRecommendationEvents } from '../src/utils/recommendationEventQueue';

jest.mock('../src/api/map', () => ({
  fetchMapGeoJSON: jest.fn(),
  fetchSavedPlacesGeoJSON: jest.fn().mockResolvedValue([]),
}));
jest.mock('../src/stores/authStore', () => ({
  useAuthStore: jest.fn(),
}));
jest.mock('../src/api/cities', () => ({
  fetchCities: jest.fn().mockResolvedValue([]),
}));
jest.mock('../src/hooks/useLocation', () => ({
  useLocation: () => null,
}));
jest.mock('../src/utils/recommendationEventQueue', () => ({
  logRecommendationEvent: jest.fn(),
  logRecommendationEvents: jest.fn(),
}));
jest.mock('expo-router', () => ({
  useRouter: () => ({ push: jest.fn() }),
}));
jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  ImpactFeedbackStyle: { Light: 'light', Medium: 'medium' },
}));

const mockedFetch = fetchMapGeoJSON as jest.MockedFunction<typeof fetchMapGeoJSON>;
const mockedSavedFetch = fetchSavedPlacesGeoJSON as jest.MockedFunction<typeof fetchSavedPlacesGeoJSON>;
const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;
const mockedLogOne = logRecommendationEvent as jest.Mock;
const mockedLogMany = logRecommendationEvents as jest.Mock;

const SF_CITY = { id: 'city-sf', name: 'San Francisco', slug: 'san-francisco', lat: 37.7749, lng: -122.4194 };

const SOLO_FEATURE = {
  id: 'place-solo', name: 'Boudin Sourdough', coordinate: { lat: 37.7871, lng: -122.4075 },
  tier: 'solid' as const, rank_score: 0.32, price_tier: null, image: null, category: 'Breakfast', has_menu: false,
};

// Three features close enough together (well within one grid cell at the
// initial region's zoom, and clearly mid-cell rather than straddling a
// grid-line boundary) to merge into a single cluster point.
const CLUSTERED_FEATURES = [
  { id: 'place-c1', name: 'A', coordinate: { lat: 37.70131, lng: -122.30131 }, tier: 'trusted' as const, rank_score: 0.4, price_tier: null, image: null, category: null, has_menu: false },
  { id: 'place-c2', name: 'B', coordinate: { lat: 37.70132, lng: -122.30132 }, tier: 'trusted' as const, rank_score: 0.4, price_tier: null, image: null, category: null, has_menu: false },
  { id: 'place-c3', name: 'C', coordinate: { lat: 37.70133, lng: -122.30133 }, tier: 'trusted' as const, rank_score: 0.4, price_tier: null, image: null, category: null, has_menu: false },
];

describe('MapScreen — Recommendation Ledger instrumentation', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useCityStore.setState({ selectedCity: SF_CITY, cities: [SF_CITY] });
    mockedFetch.mockResolvedValue([SOLO_FEATURE]);
    mockedSavedFetch.mockResolvedValue([]);
    mockedUseAuthStore.mockImplementation((selector: (s: { user: unknown }) => unknown) =>
      selector({ user: null }),
    );
  });

  it('logs one bounded, positioned impression batch after the settled initial fetch, with a stable session id and no raw coordinates', async () => {
    render(<MapScreen />);
    await waitFor(() => expect(mockedLogMany).toHaveBeenCalled());

    const batch = mockedLogMany.mock.calls[0][0];
    expect(batch).toHaveLength(1);
    expect(batch[0]).toMatchObject({
      surface: 'map', event_type: 'impression', place_id: 'place-solo', position: 0, city_id: 'city-sf',
    });
    expect(typeof batch[0].search_session_id).toBe('string');
    // No raw lat/lng/region ever leaves this screen in a logged event.
    expect(batch[0]).not.toHaveProperty('lat');
    expect(batch[0]).not.toHaveProperty('lng');
  });

  it('logs a click on the bottom-sheet open tap, with the position from the logged impression and the same session id', async () => {
    const { getByTestId, getByLabelText } = render(<MapScreen />);
    await waitFor(() => expect(mockedLogMany).toHaveBeenCalled());
    const impressionSessionId = mockedLogMany.mock.calls[0][0][0].search_session_id;

    fireEvent.press(getByTestId('marker-place-solo'));
    // A bare pin tap (revealing the preview sheet) logs nothing by itself.
    expect(mockedLogOne).not.toHaveBeenCalled();

    fireEvent.press(getByLabelText('Open Boudin Sourdough'));
    expect(mockedLogOne).toHaveBeenCalledWith(
      expect.objectContaining({
        surface: 'map', event_type: 'click', place_id: 'place-solo', position: 0,
        city_id: 'city-sf', search_session_id: impressionSessionId,
      }),
    );
  });

  it('does not log any event for a cluster tap -- no single place_id to attribute it to', async () => {
    mockedFetch.mockResolvedValue(CLUSTERED_FEATURES);
    const { getByTestId } = render(<MapScreen />);
    await waitFor(() => expect(mockedLogMany).toHaveBeenCalled());
    mockedLogOne.mockClear();
    mockedLogMany.mockClear();

    fireEvent.press(getByTestId(/^marker-cluster-/));

    expect(mockedLogOne).not.toHaveBeenCalled();
    expect(mockedLogMany).not.toHaveBeenCalled();
  });

  it('mints a fresh session id on a city change, and logs saved-mode impressions too', async () => {
    render(<MapScreen />);
    await waitFor(() => expect(mockedLogMany).toHaveBeenCalledTimes(1));
    const firstSessionId = mockedLogMany.mock.calls[0][0][0].search_session_id;

    const OTHER_CITY = { id: 'city-nyc', name: 'New York', slug: 'nyc', lat: 40.7128, lng: -74.006 };
    mockedFetch.mockResolvedValue([{ ...SOLO_FEATURE, id: 'place-nyc' }]);
    await act(async () => {
      useCityStore.setState({ selectedCity: OTHER_CITY, cities: [SF_CITY, OTHER_CITY] });
    });
    await waitFor(() => expect(mockedLogMany).toHaveBeenCalledTimes(2));
    const secondSessionId = mockedLogMany.mock.calls[1][0][0].search_session_id;

    expect(secondSessionId).not.toBe(firstSessionId);
  });

  it('filters out a marker by category, keeps a matching one, and a filtered-in click still uses its real impression position', async () => {
    const OTHER = {
      id: 'place-other', name: 'Cafe Bistro', coordinate: { lat: 37.9, lng: -122.1 },
      tier: 'solid' as const, rank_score: 0.3, price_tier: null, image: null, category: 'Lunch', has_menu: false,
    };
    mockedFetch.mockResolvedValue([SOLO_FEATURE, OTHER]);
    const { getByTestId, getByLabelText, queryByTestId } = render(<MapScreen />);
    await waitFor(() => expect(mockedLogMany).toHaveBeenCalledTimes(1));

    fireEvent.press(getByLabelText('Filter places'));
    fireEvent.press(getByLabelText('Lunch'));

    expect(queryByTestId('marker-place-solo')).toBeNull();
    expect(getByTestId('marker-place-other')).toBeTruthy();

    fireEvent.press(getByTestId('marker-place-other'));
    fireEvent.press(getByLabelText('Open Cafe Bistro'));
    // place-other was logged at position 1 in the original (unfiltered)
    // impression batch -- the filter narrows what's rendered, not the
    // position a click reports.
    expect(mockedLogOne).toHaveBeenCalledWith(
      expect.objectContaining({ place_id: 'place-other', position: 1 }),
    );
  });
});
