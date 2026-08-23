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
import MapScreen from './map';
import { fetchMapGeoJSON } from '../../src/api/map';
import { useCityStore } from '../../src/stores/cityStore';
// Imported by relative path, not the package specifier — Jest substitutes
// this same mock file for the 'react-native-maps' import inside map.tsx
// automatically (manual __mocks__ dir), but tsc has no notion of that
// runtime swap and would otherwise type-check against the real package's
// (mock-symbol-free) types.
import { animateToRegionMock, mapViewProps } from '../../__mocks__/react-native-maps';

jest.mock('../../src/api/map', () => ({
  fetchMapGeoJSON: jest.fn(),
}));
jest.mock('../../src/api/cities', () => ({
  fetchCities: jest.fn().mockResolvedValue([]),
}));
jest.mock('../../src/hooks/useLocation', () => ({
  useLocation: () => null, // no GPS — matches the repro (default/city fallback)
}));
jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  ImpactFeedbackStyle: { Light: 'light', Medium: 'medium' },
}));

const mockedFetch = fetchMapGeoJSON as jest.MockedFunction<typeof fetchMapGeoJSON>;

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
});
