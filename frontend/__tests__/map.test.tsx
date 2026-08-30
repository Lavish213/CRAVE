// Verifies the fix for a live-confirmed production bug: the Map tab showed
// zero pins in every city because iOS MapKit fires a spurious
// onRegionChangeComplete right after mount, reporting a bogus ~1km-radius
// region that has nothing to do with the real initialRegion — and because
// that spurious fetch started (and resolved) after the mount effect's
// correct one, it won the requestIdRef race and silently overwrote real
// results with an empty response.
//
// Reproduces the exact event sequence seen in production logs:
//   1. mount (fires the real initial loadFeatures call)
//   2. spurious native onRegionChangeComplete with a tiny, wrong region
//   3. onMapReady (the documented react-native-maps fix — re-corrects the
//      region via animateToRegion)
//   4. a genuine user pan
//
// and asserts each step does what the fix claims: the spurious event is
// ignored (no second fetch, no clobbered results), onMapReady re-applies
// the correct region, and a real pan still triggers a real fetch.
import React from 'react';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';
import MapScreen, { buildClusters } from '../app/(tabs)/map';
import { fetchMapGeoJSON } from '../src/api/map';
import { useCityStore } from '../src/stores/cityStore';
import { useAuthStore } from '../src/stores/authStore';
import { fetchSavedPlacesGeoJSON } from '../src/api/map';
// Imported by relative path, not the package specifier — Jest substitutes
// this same mock file for the 'react-native-maps' import inside map.tsx
// automatically (manual __mocks__ dir), but tsc has no notion of that
// runtime swap and would otherwise type-check against the real package's
// (mock-symbol-free) types.
import { animateToRegionMock, fitToCoordinatesMock, mapViewProps } from '../__mocks__/react-native-maps';

jest.mock('../src/api/map', () => ({
  fetchMapGeoJSON: jest.fn(),
  fetchSavedPlacesGeoJSON: jest.fn().mockResolvedValue([]),
}));
jest.mock('../src/stores/authStore', () => ({
  // Mocking this avoids pulling in the real Supabase client (which needs
  // real env vars) via authStore's own import chain. A jest.fn() (rather
  // than a fixed selector result) lets individual tests control whether
  // "user" is signed in, since the "my saved places" toggle only renders
  // when it is.
  useAuthStore: jest.fn(),
}));
jest.mock('../src/api/cities', () => ({
  fetchCities: jest.fn().mockResolvedValue([]),
}));
// map.tsx now logs Recommendation Ledger events (2026-08-26) -- real
// recommendationEventQueue.ts -> recommendationEvents.ts -> client.ts ->
// lib/supabase.ts, which throws at import time outside a real app process
// (no EXPO_PUBLIC_SUPABASE_URL env var here). This test file predates
// that instrumentation and isn't about it -- mock it out rather than pull
// in the real chain. See map-instrumentation.test.tsx for the dedicated
// coverage on what actually gets logged.
jest.mock('../src/utils/recommendationEventQueue', () => ({
  logRecommendationEvent: jest.fn(),
  logRecommendationEvents: jest.fn(),
}));
jest.mock('../src/hooks/useLocation', () => ({
  useLocation: () => null, // no GPS — matches the repro (default/city fallback)
}));
jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  ImpactFeedbackStyle: { Light: 'light', Medium: 'medium' },
}));

const mockedFetch = fetchMapGeoJSON as jest.MockedFunction<typeof fetchMapGeoJSON>;
const mockedSavedFetch = fetchSavedPlacesGeoJSON as jest.MockedFunction<typeof fetchSavedPlacesGeoJSON>;
const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;

const SF_CITY = {
  id: 'city-sf',
  name: 'San Francisco',
  slug: 'san-francisco',
  lat: 37.7749,
  lng: -122.4194,
};

const REAL_FEATURE = {
  id: 'place-1',
  name: 'Boudin Sourdough',
  coordinate: { lat: 37.7871, lng: -122.4075 },
  tier: 'solid' as const,
  rank_score: 0.32,
  price_tier: null,
  image: null,
  category: 'Breakfast',
  has_menu: false,
};

describe('MapScreen — onMapReady / spurious first-region fix', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    animateToRegionMock.mockClear();
    mapViewProps.current = null;
    useCityStore.setState({ selectedCity: SF_CITY, cities: [SF_CITY] });
    mockedFetch.mockResolvedValue([REAL_FEATURE]);
    mockedSavedFetch.mockResolvedValue([]);
    mockedUseAuthStore.mockImplementation((selector: (s: { user: unknown }) => unknown) =>
      selector({ user: null }),
    );
  });

  it('ignores a spurious pre-ready onRegionChangeComplete instead of letting it clobber real results', async () => {
    render(<MapScreen />);

    // The mount effect's real, correct fetch.
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));
    const [firstCallArgs] = mockedFetch.mock.calls[0];
    expect(firstCallArgs.city_id).toBe(SF_CITY.id);
    expect(firstCallArgs.lat).toBeCloseTo(SF_CITY.lat, 5);
    expect(firstCallArgs.lng).toBeCloseTo(SF_CITY.lng, 5);
    // cityToRegion uses a fixed 0.08 delta -> a multi-km radius, nothing
    // like the bogus ~1km MapKit reported in production.
    expect(firstCallArgs.radius_km).toBeGreaterThan(5);

    // Simulate iOS MapKit's own bogus first settle event — same shape as
    // the real one confirmed in production: `radiusKm: ~1.02`.
    await act(async () => {
      mapViewProps.current.onRegionChangeComplete({
        latitude: 37.6,
        longitude: -122.6,
        latitudeDelta: 0.018,
        longitudeDelta: 0.018,
      });
      // Real time must actually pass for the debounce inside
      // handleRegionChangeComplete to have any chance of firing.
      await new Promise((r) => setTimeout(r, 600));
    });

    // The spurious event must not have triggered a second fetch at all.
    expect(mockedFetch).toHaveBeenCalledTimes(1);
  });

  it('re-applies the correct region via animateToRegion once onMapReady fires', async () => {
    render(<MapScreen />);
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));

    const callsBefore = animateToRegionMock.mock.calls.length;

    act(() => {
      mapViewProps.current.onMapReady();
    });

    expect(animateToRegionMock.mock.calls.length).toBeGreaterThan(callsBefore);
    const [region] = animateToRegionMock.mock.calls[animateToRegionMock.mock.calls.length - 1];
    expect(region.latitude).toBeCloseTo(SF_CITY.lat, 5);
    expect(region.longitude).toBeCloseTo(SF_CITY.lng, 5);
  });

  it('a genuine user pan after onMapReady still triggers a real, correctly-parameterized fetch', async () => {
    render(<MapScreen />);
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));

    // The real chronology from production: a spurious native settle event
    // fires first (always ignored — see the first test above), *then*
    // onMapReady fires and re-corrects the region.
    await act(async () => {
      mapViewProps.current.onRegionChangeComplete({
        latitude: 37.6,
        longitude: -122.6,
        latitudeDelta: 0.018,
        longitudeDelta: 0.018,
      });
      await new Promise((r) => setTimeout(r, 600));
    });
    expect(mockedFetch).toHaveBeenCalledTimes(1);

    act(() => {
      mapViewProps.current.onMapReady();
    });

    // onMapReady's own animateToRegion call is flagged programmatic, so the
    // onRegionChangeComplete it triggers must NOT count as a real pan.
    await act(async () => {
      mapViewProps.current.onRegionChangeComplete({
        latitude: SF_CITY.lat,
        longitude: SF_CITY.lng,
        latitudeDelta: 0.08,
        longitudeDelta: 0.08,
      });
      await new Promise((r) => setTimeout(r, 600));
    });
    expect(mockedFetch).toHaveBeenCalledTimes(1);

    // A real pan to a genuinely new location.
    await act(async () => {
      mapViewProps.current.onRegionChangeComplete({
        latitude: 37.9,
        longitude: -122.6,
        latitudeDelta: 0.08,
        longitudeDelta: 0.08,
      });
      await new Promise((r) => setTimeout(r, 600));
    });

    expect(mockedFetch).toHaveBeenCalledTimes(2);
    const [, secondCallArgs] = mockedFetch.mock.calls.map((c) => c[0]);
    expect(secondCallArgs.lat).toBeCloseTo(37.9, 5);
    expect(secondCallArgs.lng).toBeCloseTo(-122.6, 5);
  });

  it('shows a retryable error banner on fetch failure, and retry re-issues the same request', async () => {
    mockedFetch.mockReset();
    mockedFetch.mockRejectedValueOnce(new Error('Request failed with status code 500'));
    mockedFetch.mockResolvedValueOnce([REAL_FEATURE]);

    const { findByText } = render(<MapScreen />);

    const banner = await findByText(/could not load places/i);
    expect(banner).toBeTruthy();
    expect(mockedFetch).toHaveBeenCalledTimes(1);

    await act(async () => {
      fireEvent.press(banner);
    });

    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(2));
    const [firstArgs, secondArgs] = mockedFetch.mock.calls.map((c) => c[0]);
    expect(secondArgs.lat).toBeCloseTo(firstArgs.lat, 5);
    expect(secondArgs.lng).toBeCloseTo(firstArgs.lng, 5);
    expect(firstArgs.radius_km).toBeDefined();
    expect(secondArgs.radius_km).toBeCloseTo(firstArgs.radius_km as number, 5);
  });

  it('labels retained pins as stale when a later viewport request fails', async () => {
    mockedFetch.mockReset();
    mockedFetch.mockResolvedValueOnce([REAL_FEATURE]);
    mockedFetch.mockRejectedValueOnce(new Error('network unavailable'));

    const { findByText } = render(<MapScreen />);
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));

    await act(async () => {
      mapViewProps.current.onRegionChangeComplete({
        latitude: 37.6, longitude: -122.6, latitudeDelta: 0.018, longitudeDelta: 0.018,
      });
      await new Promise((r) => setTimeout(r, 600));
    });
    act(() => mapViewProps.current.onMapReady());
    await act(async () => {
      mapViewProps.current.onRegionChangeComplete({
        latitude: SF_CITY.lat,
        longitude: SF_CITY.lng,
        latitudeDelta: 0.08,
        longitudeDelta: 0.08,
      });
      await new Promise((r) => setTimeout(r, 600));
    });
    await act(async () => {
      mapViewProps.current.onRegionChangeComplete({
        latitude: 38.0, longitude: -122.8, latitudeDelta: 0.08, longitudeDelta: 0.08,
      });
      await new Promise((r) => setTimeout(r, 600));
    });

    expect(await findByText(/showing previously loaded places/i)).toBeTruthy();
  });
});

describe('MapScreen — clustering resolves as you zoom in', () => {
  // Real bug, confirmed live: MIN_CELL_SIZE_DEG previously floored at
  // 0.0008 (~70-90m), so 3+ places within that distance of each other
  // could never be split into individual pins no matter how far a user
  // zoomed -- pinch or repeated cluster-tap alike, since the cluster-tap
  // zoom step had its own floor that was hit first. These three points
  // are ~13-26m apart: close enough to cluster at a city-wide zoom
  // (longitudeDelta 0.08, cellSize 0.002) but, after the fix, far enough
  // apart to separate into individual pins once truly zoomed in
  // (longitudeDelta 0.001, cellSize now 0.00005 -- previously it would
  // have stayed floored at 0.0008 and kept clustering these three).
  const NEARBY_A = { ...REAL_FEATURE, id: 'nearby-a', coordinate: { lat: 37.0, lng: -122.0 } };
  const NEARBY_B = { ...REAL_FEATURE, id: 'nearby-b', coordinate: { lat: 37.0, lng: -121.99985 } };
  const NEARBY_C = { ...REAL_FEATURE, id: 'nearby-c', coordinate: { lat: 37.0, lng: -121.9997 } };

  beforeEach(() => {
    jest.clearAllMocks();
    animateToRegionMock.mockClear();
    mapViewProps.current = null;
    useCityStore.setState({ selectedCity: SF_CITY, cities: [SF_CITY] });
    mockedFetch.mockResolvedValue([NEARBY_A, NEARBY_B, NEARBY_C]);
    mockedSavedFetch.mockResolvedValue([]);
    mockedUseAuthStore.mockImplementation((selector: (s: { user: unknown }) => unknown) =>
      selector({ user: null }),
    );
  });

  it('clusters three nearby places at a city-wide zoom, then splits them into individual pins once zoomed in', async () => {
    const { getByTestId, queryByTestId } = render(<MapScreen />);
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));

    // At the default city-wide region, all three fall in one grid cell.
    expect(getByTestId(/^marker-cluster-/)).toBeTruthy();
    expect(queryByTestId('marker-nearby-a')).toBeNull();
    expect(queryByTestId('marker-nearby-b')).toBeNull();
    expect(queryByTestId('marker-nearby-c')).toBeNull();

    // The very first onRegionChangeComplete after mount is always ignored
    // (iOS MapKit's own spurious-first-settle quirk -- see the describe
    // block above) -- consume it with a throwaway value before the real
    // zoom, matching every other test in this file that simulates a pan.
    await act(async () => {
      mapViewProps.current.onRegionChangeComplete({
        latitude: 37.6, longitude: -122.6, latitudeDelta: 0.018, longitudeDelta: 0.018,
      });
      await new Promise((r) => setTimeout(r, 600));
    });

    // Zoom in to street level.
    act(() => {
      mapViewProps.current.onMapReady();
    });
    await act(async () => {
      mapViewProps.current.onRegionChangeComplete({
        latitude: 37.0,
        longitude: -122.0,
        latitudeDelta: 0.001,
        longitudeDelta: 0.001,
      });
      await new Promise((r) => setTimeout(r, 600));
    });

    // Now separated into three individually tappable pins, not one cluster.
    expect(queryByTestId(/^marker-cluster-/)).toBeNull();
    expect(getByTestId('marker-nearby-a')).toBeTruthy();
    expect(getByTestId('marker-nearby-b')).toBeTruthy();
    expect(getByTestId('marker-nearby-c')).toBeTruthy();
  });

  it('bounds city-scale visual density instead of rendering a marker cloud', () => {
    const features = Array.from({ length: 250 }, (_, i) => ({
      ...REAL_FEATURE,
      id: `dense-${i}`,
      coordinate: {
        lat: 37.74 + (i % 25) * 0.003,
        lng: -122.45 + Math.floor(i / 25) * 0.008,
      },
    }));

    const clusters = buildClusters(
      features,
      { latitude: 37.7749, longitude: -122.4194, latitudeDelta: 0.08, longitudeDelta: 0.08 },
      393,
      650,
    );

    expect(clusters.reduce((sum, cluster) => sum + cluster.count, 0)).toBe(250);
    expect(clusters.length).toBeLessThanOrEqual(60);
  });
});

describe('MapScreen — "my saved places" toggle', () => {
  const SAVED_FEATURE_A = { ...REAL_FEATURE, id: 'saved-a', coordinate: { lat: 37.79, lng: -122.40 } };
  const SAVED_FEATURE_B = { ...REAL_FEATURE, id: 'saved-b', coordinate: { lat: 37.76, lng: -122.43 } };
  // A single stable reference, not recreated per call — map.tsx's `user`
  // is a dependency of a useEffect, and a fresh object literal here on
  // every mock invocation would make React see it as "changed" on every
  // render, looping the effect forever. The real Zustand hook this mocks
  // only returns a new reference when the store's state actually changes.
  const MOCK_SIGNED_IN_USER = { id: 'user-1' };

  beforeEach(() => {
    jest.clearAllMocks();
    animateToRegionMock.mockClear();
    mapViewProps.current = null;
    useCityStore.setState({ selectedCity: SF_CITY, cities: [SF_CITY] });
    mockedFetch.mockResolvedValue([REAL_FEATURE]);
    mockedSavedFetch.mockResolvedValue([SAVED_FEATURE_A, SAVED_FEATURE_B]);
    // Signed in for this whole describe block — the toggle only renders
    // when there's a user.
    mockedUseAuthStore.mockImplementation((selector: (s: { user: unknown }) => unknown) =>
      selector({ user: MOCK_SIGNED_IN_USER }),
    );
  });

  it('does not render the toggle when signed out', async () => {
    mockedUseAuthStore.mockImplementation((selector: (s: { user: unknown }) => unknown) =>
      selector({ user: null }),
    );
    const { queryByLabelText } = render(<MapScreen />);
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));

    expect(queryByLabelText('Show my saved places')).toBeNull();
  });

  it('switching to saved mode fetches saved places and fits the map to them, not a viewport fetch', async () => {
    const { getByLabelText } = render(<MapScreen />);
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));

    await act(async () => {
      fireEvent.press(getByLabelText('Show my saved places'));
    });

    await waitFor(() => expect(mockedSavedFetch).toHaveBeenCalledTimes(1));
    // The global-catalog fetch must not have fired again for the mode switch.
    expect(mockedFetch).toHaveBeenCalledTimes(1);
    // Two saved places -> fits the map to both, rather than a single
    // animateToRegion (which is what a 0- or 1-place result would use).
    await waitFor(() => expect(fitToCoordinatesMock).toHaveBeenCalledTimes(1));
    const [coords] = fitToCoordinatesMock.mock.calls[0];
    expect(coords).toEqual([
      { latitude: SAVED_FEATURE_A.coordinate.lat, longitude: SAVED_FEATURE_A.coordinate.lng },
      { latitude: SAVED_FEATURE_B.coordinate.lat, longitude: SAVED_FEATURE_B.coordinate.lng },
    ]);
  });

  it('panning while in saved mode does not trigger a viewport-scoped fetch', async () => {
    const { getByLabelText } = render(<MapScreen />);
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));

    await act(async () => {
      fireEvent.press(getByLabelText('Show my saved places'));
    });
    await waitFor(() => expect(mockedSavedFetch).toHaveBeenCalledTimes(1));

    await act(async () => {
      mapViewProps.current.onRegionChangeComplete({
        latitude: 37.9, longitude: -122.5, latitudeDelta: 0.08, longitudeDelta: 0.08,
      });
      await new Promise((r) => setTimeout(r, 600));
    });

    // Still just the one saved-places fetch and the one original city
    // fetch from before the switch — panning in saved mode fetches nothing.
    expect(mockedSavedFetch).toHaveBeenCalledTimes(1);
    expect(mockedFetch).toHaveBeenCalledTimes(1);
  });

  it('switching back to city mode re-fetches the global catalog', async () => {
    const { getByLabelText } = render(<MapScreen />);
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));

    await act(async () => {
      fireEvent.press(getByLabelText('Show my saved places'));
    });
    await waitFor(() => expect(mockedSavedFetch).toHaveBeenCalledTimes(1));

    await act(async () => {
      fireEvent.press(getByLabelText('Show all places'));
    });

    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(2));
  });
});
