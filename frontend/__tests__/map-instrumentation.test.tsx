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
jest.mock('../src/stores/authStore', () => ({ useAuthStore: jest.fn() }));
jest.mock('../src/api/cities', () => ({ fetchCities: jest.fn().mockResolvedValue([]) }));
jest.mock('../src/hooks/useLocation', () => ({ useLocation: () => null }));
jest.mock('../src/utils/recommendationEventQueue', () => ({
  logRecommendationEvent: jest.fn(),
  logRecommendationEvents: jest.fn(),
}));
const mockPush = jest.fn();
jest.mock('expo-router', () => ({ useRouter: () => ({ push: mockPush }) }));
jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  ImpactFeedbackStyle: { Light: 'light', Medium: 'medium' },
}));

const mockedFetch = fetchMapGeoJSON as jest.MockedFunction<typeof fetchMapGeoJSON>;
const mockedSavedFetch = fetchSavedPlacesGeoJSON as jest.MockedFunction<typeof fetchSavedPlacesGeoJSON>;
const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;
const mockedLogOne = logRecommendationEvent as jest.Mock;
const mockedLogMany = logRecommendationEvents as jest.Mock;

const SF_CITY = {
  id: 'city-sf', name: 'San Francisco', slug: 'san-francisco',
  lat: 37.7749, lng: -122.4194,
};

const SOLO_FEATURE = {
  id: 'place-solo', name: 'Boudin Sourdough',
  coordinate: { lat: 37.7871, lng: -122.4075 },
  tier: 'solid' as const, rank_score: 0.32, price_tier: null,
  image: null, category: 'Breakfast', has_menu: false, has_video: false,
};

const OFFSCREEN_PREFETCHED = {
  ...SOLO_FEATURE,
  id: 'place-prefetched',
  name: 'Prefetched Outside Viewport',
  // Outside initial ±0.04° latitude viewport, but representative of the
  // wider 1.6x fetch ring returned by the mocked backend request.
  coordinate: { lat: 37.827, lng: -122.4194 },
};

const CLUSTERED_FEATURES = [
  { ...SOLO_FEATURE, id: 'place-c1', name: 'A', coordinate: { lat: 37.77510, lng: -122.41910 } },
  { ...SOLO_FEATURE, id: 'place-c2', name: 'B', coordinate: { lat: 37.77511, lng: -122.41911 } },
  { ...SOLO_FEATURE, id: 'place-c3', name: 'C', coordinate: { lat: 37.77512, lng: -122.41912 } },
];

describe('MapScreen — visible exposure instrumentation', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useCityStore.setState({ selectedCity: SF_CITY, cities: [SF_CITY] });
    mockedFetch.mockResolvedValue([SOLO_FEATURE]);
    mockedSavedFetch.mockResolvedValue([]);
    mockedUseAuthStore.mockImplementation((selector: (s: { user: unknown }) => unknown) =>
      selector({ user: null }),
    );
  });

  it('logs an impression only after a fetched feature is represented by a visible singleton pin', async () => {
    render(<MapScreen />);
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(mockedLogMany).toHaveBeenCalledTimes(1));

    const batch = mockedLogMany.mock.calls[0][0];
    expect(batch).toHaveLength(1);
    expect(batch[0]).toMatchObject({
      surface: 'map',
      event_type: 'impression',
      place_id: 'place-solo',
      position: 0,
      city_id: 'city-sf',
    });
    expect(typeof batch[0].search_session_id).toBe('string');
    expect(batch[0]).not.toHaveProperty('lat');
    expect(batch[0]).not.toHaveProperty('lng');
  });

  it('does not count a fetched feature in the prefetch ring outside the viewport as an impression', async () => {
    mockedFetch.mockResolvedValue([OFFSCREEN_PREFETCHED]);
    render(<MapScreen />);

    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));
    await act(async () => { await Promise.resolve(); });

    expect(mockedLogMany).not.toHaveBeenCalled();
  });

  it('does not fabricate individual impressions for places hidden inside a cluster', async () => {
    mockedFetch.mockResolvedValue(CLUSTERED_FEATURES);
    const { getByTestId } = render(<MapScreen />);

    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));
    expect(await waitFor(() => getByTestId(/^marker-cluster-/))).toBeTruthy();
    expect(mockedLogMany).not.toHaveBeenCalled();

    mockedLogOne.mockClear();
    fireEvent.press(getByTestId(/^marker-cluster-/));
    expect(mockedLogOne).not.toHaveBeenCalled();
  });

  it('logs a detail click with the position from the currently visible-pin set and same session id', async () => {
    const { getByTestId, getByLabelText } = render(<MapScreen />);
    await waitFor(() => expect(mockedLogMany).toHaveBeenCalledTimes(1));
    const impressionSessionId = mockedLogMany.mock.calls[0][0][0].search_session_id;

    fireEvent.press(getByTestId('marker-place-solo'));
    expect(mockedLogOne).not.toHaveBeenCalled();

    fireEvent.press(getByLabelText('Open Boudin Sourdough'));
    expect(mockedLogOne).toHaveBeenCalledWith(expect.objectContaining({
      surface: 'map',
      event_type: 'click',
      place_id: 'place-solo',
      position: 0,
      city_id: 'city-sf',
      search_session_id: impressionSessionId,
    }));
    expect(mockPush).toHaveBeenCalledWith('/place/place-solo');
  });

  it('mints a fresh session and never attributes old-city pins to the new city', async () => {
    render(<MapScreen />);
    await waitFor(() => expect(mockedLogMany).toHaveBeenCalledTimes(1));
    const firstSessionId = mockedLogMany.mock.calls[0][0][0].search_session_id;

    const NYC = { id: 'city-nyc', name: 'New York', slug: 'nyc', lat: 40.7128, lng: -74.006 };
    mockedFetch.mockResolvedValue([{
      ...SOLO_FEATURE,
      id: 'place-nyc',
      name: 'NYC Place',
      coordinate: { lat: 40.713, lng: -74.005 },
    }]);

    await act(async () => {
      useCityStore.setState({ selectedCity: NYC, cities: [SF_CITY, NYC] });
    });

    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(mockedLogMany).toHaveBeenCalledTimes(2));
    const secondBatch = mockedLogMany.mock.calls[1][0];

    expect(secondBatch).toEqual([
      expect.objectContaining({ place_id: 'place-nyc', city_id: 'city-nyc' }),
    ]);
    expect(secondBatch[0].search_session_id).not.toBe(firstSessionId);
    expect(mockedLogMany.mock.calls.flatMap((call) => call[0]).filter(
      (event) => event.city_id === 'city-nyc' && event.place_id === 'place-solo',
    )).toHaveLength(0);
  });

  it('filters before exposure and reports a click position in the currently visible pin set', async () => {
    const OTHER = {
      ...SOLO_FEATURE,
      id: 'place-other',
      name: 'Cafe Bistro',
      coordinate: { lat: 37.755, lng: -122.44 },
      category: 'Lunch',
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
    expect(mockedLogOne).toHaveBeenCalledWith(
      expect.objectContaining({ place_id: 'place-other', position: 0 }),
    );
  });
});
