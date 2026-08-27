import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import MapView, { Marker, Region } from 'react-native-maps';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { fetchMapGeoJSON, fetchSavedPlacesGeoJSON, NormalizedMapFeature } from '../../src/api/map';
import { useCityStore } from '../../src/stores/cityStore';
import { useAuthStore } from '../../src/stores/authStore';
import { useLocation } from '../../src/hooks/useLocation';
import { Colors, Radius, Shadows, Spacing } from '../../src/constants/colors';
import { CitySelectorStrip } from '../../src/components/CitySelectorStrip';
import { MapMarkerDot, MapClusterDot } from '../../src/components/MapMarker';
import { MapBottomSheet } from '../../src/components/MapBottomSheet';
import { logRecommendationEvent, logRecommendationEvents } from '../../src/utils/recommendationEventQueue';
import { FilterSheet, FilterState, EMPTY_FILTERS, hasActiveFilters } from '../../src/components/FilterSheet';

// Recommendation Ledger, surface='map'. Deliberately narrower than the
// other surfaces' instrumentation: log a bounded impression batch only
// when a settled/debounced region actually produces a fresh fetch (the
// coverage-cache/stale-region guards above already skip a fetch for
// already-seen ground -- no new impression fires for that skip, since
// nothing new was shown). No raw lat/lng/region ever gets logged, only
// place_id + tier context -- this is meant to reconstruct "what was
// shown and picked," not a location trail.
//
// Only one click point: the bottom-sheet row tap (which already
// performs the place-detail navigation in the existing code -- see
// onOpen below). A bare pin tap that only reveals the preview sheet is
// NOT separately logged -- in real usage a pin gets tapped, glanced at,
// and often dismissed without opening; logging every glance as a full
// 'click' would inflate the signal with "just looking" taps the same
// way logging every pan would. Cluster taps get no event at all -- a
// cluster has no single place_id, it's a zoom gesture, not a selection.
//
// No new column: reuses the existing `search_session_id` field (see
// backend's recommendation_event.py) as a generic "stable id for one
// continuous surface-interaction session," not literally search-only
// despite the name -- reconstruction genuinely doesn't need a new
// column, just a broader documented use of this one. Minted fresh
// whenever the city or view mode changes (a deliberate restart of what's
// being explored), not on every pan.
const MAX_LOGGED_MAP_FEATURES = 30;

function _makeMapSessionId(): string {
  return `map_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
}

// How long to wait after the user stops panning/zooming before refetching —
// avoids firing a request on every intermediate frame of a gesture.
const REGION_FETCH_DEBOUNCE_MS = 500;

// Fetch a wider radius than the exact visible viewport so a small pan lands
// on already-loaded pins instantly instead of showing a fresh loading state
// — previously every fetch matched the viewport exactly, so any pan at all
// (even a few hundred meters) required a brand-new round trip before pins
// reappeared.
const PREFETCH_RADIUS_MULTIPLIER = 1.6;

// Grid cell size clustering constants — cell size scales with the visible
// longitude span so clustering density adapts to zoom level.
//
// MIN_CELL_SIZE_DEG was previously 0.0008 (~70-90m on the ground) as a
// hard floor -- meant to guard against a pathological near-zero cell
// size, but in practice it meant cellSize stopped shrinking well before
// a user finished zooming in, so any 3+ places within ~80m of each other
// (a food hall, a plaza, a busy block) could never be split into
// individual pins no matter how far you zoomed, pinch or cluster-tap
// alike. Confirmed live: this is what read as "over-clustered" and
// "can't tap pins" -- not a tap-registration bug (see the Marker
// onPress stopPropagation fix elsewhere in this file), but places
// genuinely having no individual pin to tap. Dropped to 0.00005
// (~5m) -- small enough to let cellSize keep shrinking all the way to
// "basically never clusters at street-level zoom" (the actually correct
// behavior), while still guarding against a literal zero/near-zero
// region.longitudeDelta producing a degenerate cell size.
const MIN_CLUSTER_SIZE = 3;
const MIN_CELL_SIZE_DEG = 0.00005;

// Floor for the region a cluster tap zooms into. Previously 0.003 -- itself
// ~4x bigger than the old cell-size floor above, so tapping a cluster hit
// its own ceiling before zooming in far enough for the (now-fixed) cell
// size to ever matter. Lowered so repeated cluster taps can actually reach
// street-level separation instead of visibly stalling.
const CLUSTER_TAP_MIN_DELTA = 0.0004;

const TIER_COLORS: Record<string, string> = {
  elite:   Colors.tierCravePick,
  trusted: Colors.tierGem,
  solid:   Colors.tierSolid,
  default: Colors.tierNew,
};

const DEFAULT_REGION: Region = {
  latitude: 37.8044,
  longitude: -122.2712,
  latitudeDelta: 0.08,
  longitudeDelta: 0.08,
};

function cityToRegion(lat: number, lng: number): Region {
  return { latitude: lat, longitude: lng, latitudeDelta: 0.08, longitudeDelta: 0.08 };
}

// Approximate the on-screen search radius (km) implied by a map region's
// current zoom level, so panning/zooming actually changes what gets fetched
// instead of always querying the same fixed 5km box.
function radiusKmForRegion(region: Region): number {
  const latRad = (region.latitude * Math.PI) / 180;
  const kmPerLngDegree = 111.32 * Math.cos(latRad);
  const widthKm = region.longitudeDelta * kmPerLngDegree;
  const heightKm = region.latitudeDelta * 111.32;
  const radius = Math.max(widthKm, heightKm) / 2;
  return Math.min(50, Math.max(0.5, radius));
}

// What we actually fetch: the visible radius padded by
// PREFETCH_RADIUS_MULTIPLIER, re-clamped to the API's 50km max, so a pan
// within that margin needs no new request at all.
function prefetchRadiusKmForRegion(region: Region): number {
  return Math.min(50, radiusKmForRegion(region) * PREFETCH_RADIUS_MULTIPLIER);
}

// Equirectangular approximation, consistent with radiusKmForRegion's own —
// accurate enough at map-pan scale, used to check whether a pan landed
// somewhere the last successful fetch already covers.
function distanceKm(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const latRad = ((lat1 + lat2) / 2 * Math.PI) / 180;
  const kmPerLngDegree = 111.32 * Math.cos(latRad);
  const dLat = (lat2 - lat1) * 111.32;
  const dLng = (lng2 - lng1) * kmPerLngDegree;
  return Math.sqrt(dLat * dLat + dLng * dLng);
}

// radiusKmForRegion is half the LONGER side — the right measure for how
// much to fetch, but too small for a coverage check: a viewport's actual
// corners sit at the half-DIAGONAL distance from center, which is always
// >= half the longer side. Using radiusKmForRegion here could call a
// viewport "covered" while its corners still poke outside the cached
// circle. This is the stricter, correct value for that comparison only.
function coverageRadiusKmForRegion(region: Region): number {
  const latRad = (region.latitude * Math.PI) / 180;
  const widthKm = region.longitudeDelta * 111.32 * Math.cos(latRad);
  const heightKm = region.latitudeDelta * 111.32;
  return Math.hypot(widthKm, heightKm) / 2;
}

interface FetchCoverage {
  lat: number;
  lng: number;
  radiusKm: number;
}

// True when everything within visibleRadiusKm of (lat, lng) already sits
// inside a previously-fetched circle — i.e. this pan needs no new request
// at all, not even the padded prefetch one.
function isCoveredByPriorFetch(
  lat: number,
  lng: number,
  visibleRadiusKm: number,
  coverage: FetchCoverage | null
): boolean {
  if (!coverage) return false;
  return distanceKm(lat, lng, coverage.lat, coverage.lng) + visibleRadiusKm <= coverage.radiusKm;
}

interface SelectedFeature {
  id: string;
  name: string;
  tier: string;
  image?: string;
  category?: string;
}

interface ClusterPoint {
  key: string;
  latitude: number;
  longitude: number;
  count: number;
  feature?: NormalizedMapFeature;
}

// Simple grid-based clustering: bucket features into cells sized relative to
// the current zoom level, and merge cells with 3+ points into one cluster pin.
function buildClusters(features: NormalizedMapFeature[], region: Region): ClusterPoint[] {
  const cellSize = Math.max(region.longitudeDelta / 40, MIN_CELL_SIZE_DEG);
  const cells = new Map<string, NormalizedMapFeature[]>();

  for (const f of features) {
    const cellX = Math.floor(f.coordinate.lng / cellSize);
    const cellY = Math.floor(f.coordinate.lat / cellSize);
    const key = `${cellX}:${cellY}`;
    const bucket = cells.get(key);
    if (bucket) bucket.push(f);
    else cells.set(key, [f]);
  }

  const clusters: ClusterPoint[] = [];
  for (const [key, bucket] of cells) {
    if (bucket.length < MIN_CLUSTER_SIZE) {
      bucket.forEach((f, i) => {
        clusters.push({
          key: `${key}:${i}`,
          latitude: f.coordinate.lat,
          longitude: f.coordinate.lng,
          count: 1,
          feature: f,
        });
      });
      continue;
    }

    const avgLat = bucket.reduce((sum, f) => sum + f.coordinate.lat, 0) / bucket.length;
    const avgLng = bucket.reduce((sum, f) => sum + f.coordinate.lng, 0) / bucket.length;
    clusters.push({ key, latitude: avgLat, longitude: avgLng, count: bucket.length });
  }

  return clusters;
}

export default function MapScreen() {
  const router = useRouter();
  const selectedCity = useCityStore((s) => s.selectedCity);
  const userLocation = useLocation();
  const user = useAuthStore((s) => s.user);
  const mapRef = useRef<MapView>(null);

  // 'city' = the global catalog (existing behavior). 'saved' = just this
  // user's own saved places — the personal, curated map both Beli and
  // Biter advertise as a core feature, which this screen never had before
  // (it only ever showed the global catalog).
  const [viewMode, setViewMode] = useState<'city' | 'saved'>('city');
  const [filterVisible, setFilterVisible] = useState(false);
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);

  // True for the one onRegionChangeComplete event caused by our own
  // animateToRegion call (city change / cluster tap) — lets us skip firing a
  // redundant viewport fetch for a move the user didn't make.
  const programmaticMoveRef = useRef(false);
  const fetchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Live-confirmed via device logs: the very first onRegionChangeComplete
  // firing after MapView mounts reports a bogus, heavily-zoomed-in transient
  // region (~1km radius) that has nothing to do with `initialRegion` — an
  // iOS MapKit/react-native-maps quirk where the view reports its settle
  // state before layout has actually finished applying the requested
  // region. Because that spurious event starts its fetch AFTER the mount
  // effect's correct one, it wins the requestIdRef race and silently
  // clobbers the real results with an empty response — the map showed zero
  // pins in every city, every time, confirmed against real production data
  // that Feed/Search both loaded correctly in the same session. Skipping
  // only this one first call is safe: the mount effect below already
  // performs the real initial load.
  const hasHandledFirstRegionRef = useRef(false);

  const [features, setFeatures] = useState<NormalizedMapFeature[]>([]);
  const [selectedFeature, setSelectedFeature] = useState<SelectedFeature | null>(null);
  const [mapLoading, setMapLoading] = useState(false);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [mapError, setMapError] = useState(false);

  // Bumped on every loadFeatures call — an in-flight request whose result
  // arrives after a newer one has already resolved gets discarded instead
  // of overwriting it. Without this, mount fires a load at the default/
  // fallback location and GPS resolving fires a second one moments later;
  // if the first (default-location) request is the slower of the two and
  // fails after the second already succeeded, its late .catch() clobbered
  // mapError back to true even though pins from the newer request were
  // already showing — exactly the "pins visible + error banner" state
  // confirmed on a real device.
  const requestIdRef = useRef(0);

  // The most recent successful fetch's center + actual fetched radius —
  // lets a subsequent pan skip firing a request at all when the visible
  // area is already fully inside this circle, instead of always refetching
  // on every debounced region change regardless of coverage.
  const lastFetchCoverageRef = useRef<FetchCoverage | null>(null);

  // Recommendation Ledger bookkeeping. lastImpressionIdsRef holds the
  // ordered place_ids from the most recently *logged* impression batch,
  // so a bottom-sheet click can report its real position within what was
  // actually shown (and logged) rather than an arbitrary array index --
  // same pattern as Craves' matched-only position lookup.
  const mapSessionIdRef = useRef(_makeMapSessionId());
  const lastImpressionIdsRef = useRef<string[]>([]);

  // Re-mints on a deliberate restart of what's being explored (a new
  // city picked, or switching city<->saved), not on every incidental
  // mapLat/mapLng change (e.g. GPS resolving shortly after mount would
  // otherwise also re-fire this if it depended on those instead).
  // Skips the very first run -- mapSessionIdRef already has its initial
  // value from useRef() above, minting again here would just discard it
  // for no reason on mount.
  const isFirstSessionMintRef = useRef(true);
  useEffect(() => {
    if (isFirstSessionMintRef.current) {
      isFirstSessionMintRef.current = false;
      return;
    }
    mapSessionIdRef.current = _makeMapSessionId();
  }, [selectedCity?.id, viewMode]);

  // Shared by loadFeatures and loadSavedPlaces below -- both are real
  // "here's what's now shown on the map" moments. No rank_percentile:
  // NormalizedMapFeature only carries an absolute rank_score, not a
  // catalog percentile the way Feed/Search places do -- left null rather
  // than fabricated from a conversion that doesn't exist server-side.
  const logMapImpression = useCallback(
    (normalized: NormalizedMapFeature[]) => {
      if (normalized.length === 0) {
        lastImpressionIdsRef.current = [];
        return;
      }
      const bounded = normalized.slice(0, MAX_LOGGED_MAP_FEATURES);
      lastImpressionIdsRef.current = bounded.map((f) => f.id);
      logRecommendationEvents(
        bounded.map((f, i) => ({
          surface: 'map',
          event_type: 'impression',
          place_id: f.id,
          position: i,
          city_id: selectedCity?.id ?? null,
          search_session_id: mapSessionIdRef.current,
        })),
      );
    },
    [selectedCity?.id],
  );

  // Effective center: city > user location > default
  const mapLat = selectedCity?.lat ?? userLocation?.lat ?? DEFAULT_REGION.latitude;
  const mapLng = selectedCity?.lng ?? userLocation?.lng ?? DEFAULT_REGION.longitude;

  const initialRegion = cityToRegion(mapLat, mapLng);
  const [mapRegion, setMapRegion] = useState<Region>(initialRegion);

  // Last-attempted params (unlike lastFetchCoverageRef, set regardless of
  // success/failure) — lets a "Retry" tap redo the exact request that just
  // failed instead of needing the user to pan the map to trigger a new one.
  const lastAttemptRef = useRef<FetchCoverage | null>(null);

  const loadFeatures = useCallback(
    (lat: number, lng: number, radiusKm: number) => {
      const myRequestId = ++requestIdRef.current;
      lastAttemptRef.current = { lat, lng, radiusKm };
      setMapError(false);
      setMapLoading(true);
      fetchMapGeoJSON({
        city_id: selectedCity?.id,
        lat,
        lng,
        radius_km: radiusKm,
      })
        .then((normalized) => {
          if (myRequestId !== requestIdRef.current) return;
          if (__DEV__) console.log('[MAP] FEATURES_LOADED', { count: normalized.length, lat, lng, radiusKm, cityId: selectedCity?.id, sample: normalized[0] ? { id: normalized[0].id, lat: normalized[0].coordinate.lat, lng: normalized[0].coordinate.lng, tier: normalized[0].tier } : null });
          setFeatures(normalized);
          setMapLoaded(true);
          lastFetchCoverageRef.current = { lat, lng, radiusKm };
          logMapImpression(normalized);
        })
        .catch((err) => {
          if (myRequestId !== requestIdRef.current) return;
          // Was completely silent before — "Could not load places" gave no
          // way to tell a timeout from a 4xx/5xx from a network drop.
          if (__DEV__) console.log('[MAP] LOAD_FAILED', { lat, lng, radiusKm, status: err?.response?.status, message: err?.message, data: err?.response?.data });
          setMapError(true);
        })
        .finally(() => {
          if (myRequestId !== requestIdRef.current) return;
          setMapLoading(false);
        });
    },
    [selectedCity?.id, logMapImpression]
  );

  // Initial load + reload on city change (or GPS location resolving).
  // Only in 'city' mode — while browsing "my places", a city selection
  // elsewhere (or GPS resolving) must not silently steal the map back to
  // the global catalog; re-running when viewMode flips back to 'city' is
  // what the dependency on it is for.
  useEffect(() => {
    if (viewMode !== 'city') return;
    // A pan-triggered debounce scheduled just before this fires would
    // otherwise invoke a stale loadFeatures closure bound to the previous
    // city/region once its timer elapses — since it calls loadFeatures
    // after this effect's call, it would win the requestIdRef race and
    // overwrite these correct, newer results with the old city's pins.
    if (fetchDebounceRef.current) {
      clearTimeout(fetchDebounceRef.current);
      fetchDebounceRef.current = null;
    }
    // Without this, a failed load for the new city leaves the previous
    // city's pins on screen with features.length still > 0 — which now
    // (correctly, for the already-covered-viewport case) suppresses the
    // error banner entirely, silently showing the wrong city's data with
    // no indication anything went wrong.
    lastFetchCoverageRef.current = null;
    setFeatures([]);
    setMapLoaded(false);
    loadFeatures(mapLat, mapLng, prefetchRadiusKmForRegion(cityToRegion(mapLat, mapLng)));
  }, [selectedCity?.id, mapLat, mapLng, loadFeatures, viewMode]);

  // Recenter the map on city change — flagged as programmatic so the
  // resulting onRegionChangeComplete doesn't trigger a duplicate fetch.
  // Skipped in 'saved' mode for the same reason as the effect above.
  useEffect(() => {
    if (viewMode !== 'city') return;
    const region = cityToRegion(mapLat, mapLng);
    programmaticMoveRef.current = true;
    setMapRegion(region);
    mapRef.current?.animateToRegion(region, 500);
  }, [selectedCity?.id, mapLat, mapLng, viewMode]);

  // Loads the signed-in user's saved places and fits the map to them.
  // Never viewport-scoped (unlike loadFeatures) — a personal list is
  // small enough to fetch in full every time. Factored out of the
  // mode-change effect below so handleRetryMap can also call it.
  const loadSavedPlaces = useCallback(() => {
    const myRequestId = ++requestIdRef.current;
    setMapError(false);
    setMapLoading(true);
    fetchSavedPlacesGeoJSON()
      .then((normalized) => {
        if (myRequestId !== requestIdRef.current) return;
        if (__DEV__) console.log('[MAP] SAVED_FEATURES_LOADED', { count: normalized.length });
        setFeatures(normalized);
        setMapLoaded(true);
        if (normalized.length === 1) {
          const only = normalized[0];
          const region = cityToRegion(only.coordinate.lat, only.coordinate.lng);
          programmaticMoveRef.current = true;
          setMapRegion(region);
          mapRef.current?.animateToRegion(region, 400);
        } else if (normalized.length > 1) {
          const coords = normalized.map((f) => ({
            latitude: f.coordinate.lat,
            longitude: f.coordinate.lng,
          }));
          programmaticMoveRef.current = true;
          mapRef.current?.fitToCoordinates(coords, {
            edgePadding: { top: 80, right: 60, bottom: 140, left: 60 },
            animated: true,
          });
        }
        logMapImpression(normalized);
      })
      .catch((err) => {
        if (myRequestId !== requestIdRef.current) return;
        if (__DEV__) console.log('[MAP] SAVED_LOAD_FAILED', { message: err?.message, status: err?.response?.status });
        setMapError(true);
      })
      .finally(() => {
        if (myRequestId !== requestIdRef.current) return;
        setMapLoading(false);
      });
  }, [logMapImpression]);

  useEffect(() => {
    if (viewMode !== 'saved') return;
    if (!user) {
      // Shouldn't happen — the toggle only renders when signed in — but
      // fail safe back to the global catalog rather than showing an
      // auth-error state on the map.
      setViewMode('city');
      return;
    }
    setFeatures([]);
    setMapLoaded(false);
    loadSavedPlaces();
  }, [viewMode, user, loadSavedPlaces]);

  // Cross-checked against react-native-maps' own long-documented iOS bug
  // class (their issue tracker: #1507, #3212, #4244, #4420, #5645 — spanning
  // years) — `initialRegion` is frequently not honored correctly on iOS: the
  // native view can settle at some other zoom/position entirely regardless
  // of what was requested, which is consistent with what we saw live here
  // (~1km reported radius vs. the real ~7km initialRegion). The effect above
  // already tries to correct this via animateToRegion, but it fires from a
  // dependency-change effect that runs immediately after the JS render —
  // before the native map view has actually finished initializing, so
  // `mapRef.current` can still be unset and the call silently no-ops. The
  // library's own documented workaround for this exact class of bug is to
  // redo the correction from `onMapReady`, which fires once the native view
  // has genuinely finished initializing — guaranteeing the ref is live.
  const handleMapReady = useCallback(() => {
    const region = cityToRegion(mapLat, mapLng);
    programmaticMoveRef.current = true;
    setMapRegion(region);
    mapRef.current?.animateToRegion(region, 300);
  }, [mapLat, mapLng]);

  // Clear any pending debounced fetch on unmount.
  useEffect(() => {
    return () => {
      if (fetchDebounceRef.current) clearTimeout(fetchDebounceRef.current);
    };
  }, []);

  const handleRegionChangeComplete = useCallback(
    (region: Region) => {
      if (!hasHandledFirstRegionRef.current) {
        hasHandledFirstRegionRef.current = true;
        return;
      }

      setMapRegion(region);

      if (programmaticMoveRef.current) {
        programmaticMoveRef.current = false;
        return;
      }

      // Exploring your saved pins by panning shouldn't trigger a fetch —
      // the whole personal list is already loaded; there's nothing new a
      // viewport-scoped request would find.
      if (viewMode !== 'city') return;

      if (fetchDebounceRef.current) clearTimeout(fetchDebounceRef.current);
      fetchDebounceRef.current = setTimeout(() => {
        const visibleRadiusKm = coverageRadiusKmForRegion(region);
        if (isCoveredByPriorFetch(region.latitude, region.longitude, visibleRadiusKm, lastFetchCoverageRef.current)) {
          if (__DEV__) console.log('[MAP] SKIP_FETCH_ALREADY_COVERED', { lat: region.latitude, lng: region.longitude, visibleRadiusKm });
          // Still bump this so an older in-flight request for a different
          // region (panned away from, now panned back to cached ground)
          // can't land later and overwrite these still-valid cached pins —
          // otherwise skipping the fetch here does nothing to stop that
          // stale response from winning once it finally resolves.
          requestIdRef.current += 1;
          setMapLoading(false);
          setMapError(false);
          return;
        }
        loadFeatures(region.latitude, region.longitude, prefetchRadiusKmForRegion(region));
      }, REGION_FETCH_DEBOUNCE_MS);
    },
    [loadFeatures, viewMode]
  );

  // Derived from what's actually loaded (this region's fetch, or the
  // saved-places layer), not a global catalog-wide list -- same fix as
  // Feed/Search's filter chips.
  const availableCategories = useMemo(() => {
    const names = new Set<string>();
    for (const f of features) {
      if (f.category) names.add(f.category);
    }
    return Array.from(names);
  }, [features]);

  // A view-level narrowing of what's already fetched, applied before
  // clustering so a filtered-out place never contributes to a cluster's
  // count/center either. NormalizedMapFeature carries a single `category`
  // string, not the categories[] array Feed/Search's places have, so the
  // match here is `===` against any selected category, not `.some(...)`.
  const filteredFeatures = useMemo(() => {
    if (!hasActiveFilters(filters)) return features;
    return features.filter((f) => {
      if (filters.priceTiers.length > 0 && (f.price_tier == null || !filters.priceTiers.includes(f.price_tier))) return false;
      if (filters.categories.length > 0 && (!f.category || !filters.categories.includes(f.category))) return false;
      return true;
    });
  }, [features, filters]);

  const clusters = useMemo(() => buildClusters(filteredFeatures, mapRegion), [filteredFeatures, mapRegion]);

  // Snap back to GPS regardless of how far the user has panned — the map
  // otherwise has no way back to "where I actually am" once you've explored
  // away from it, short of switching cities.
  const handleRecenter = useCallback(() => {
    if (!userLocation) return;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    const region = cityToRegion(userLocation.lat, userLocation.lng);
    programmaticMoveRef.current = true;
    setMapRegion(region);
    mapRef.current?.animateToRegion(region, 500);
  }, [userLocation]);

  // Re-runs the exact request that just failed, instead of forcing the user
  // to pan the map (which may not even be possible if they can't tell where
  // real data exists) just to get another attempt.
  const handleRetryMap = useCallback(() => {
    if (viewMode === 'saved') {
      loadSavedPlaces();
      return;
    }
    const attempt = lastAttemptRef.current;
    if (attempt) {
      loadFeatures(attempt.lat, attempt.lng, attempt.radiusKm);
    } else {
      loadFeatures(mapLat, mapLng, prefetchRadiusKmForRegion(cityToRegion(mapLat, mapLng)));
    }
  }, [viewMode, loadSavedPlaces, loadFeatures, mapLat, mapLng]);

  return (
    <View style={styles.container}>
      <MapView
        ref={mapRef}
        style={styles.map}
        initialRegion={initialRegion}
        mapType="mutedStandard"
        onPress={() => setSelectedFeature(null)}
        onRegionChangeComplete={handleRegionChangeComplete}
        onMapReady={handleMapReady}
      >
        {clusters.map((c) => {
          if (c.count > 1) {
            return (
              <Marker
                key={c.key}
                testID={`marker-cluster-${c.key}`}
                coordinate={{ latitude: c.latitude, longitude: c.longitude }}
                onPress={(e) => {
                  // Without this, the same tap also bubbles to MapView's
                  // own onPress (which nulls selectedFeature) -- a real,
                  // confirmed bug: a marker tap could reveal (or, for a
                  // cluster, start zooming into) then immediately undo
                  // itself in the same gesture, looking like the tap did
                  // nothing at all.
                  e.stopPropagation();
                  Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                  const zoomed: Region = {
                    latitude: c.latitude,
                    longitude: c.longitude,
                    latitudeDelta: Math.max(mapRegion.latitudeDelta / 2.5, CLUSTER_TAP_MIN_DELTA),
                    longitudeDelta: Math.max(mapRegion.longitudeDelta / 2.5, CLUSTER_TAP_MIN_DELTA),
                  };
                  programmaticMoveRef.current = true;
                  setMapRegion(zoomed);
                  mapRef.current?.animateToRegion(zoomed, 300);
                }}
                tracksViewChanges={false}
              >
                <MapClusterDot count={c.count} />
              </Marker>
            );
          }

          const f = c.feature!;
          const color = TIER_COLORS[f.tier] ?? TIER_COLORS.default;
          return (
            <Marker
              key={c.key}
              testID={`marker-${f.id}`}
              coordinate={{ latitude: f.coordinate.lat, longitude: f.coordinate.lng }}
              onPress={(e) => {
                // See the cluster Marker's identical comment above.
                e.stopPropagation();
                Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                setSelectedFeature({
                  id: f.id,
                  name: f.name,
                  tier: f.tier,
                  image: f.image ?? undefined,
                  category: f.category ?? undefined,
                });
              }}
              tracksViewChanges={false}
            >
              <MapMarkerDot color={color} />
            </Marker>
          );
        })}
      </MapView>

      <View style={styles.cityStrip}>
        <View style={styles.cityStripScroll}>
          <CitySelectorStrip />
        </View>
        {features.length > 0 && (
          <TouchableOpacity
            style={styles.filterBtn}
            onPress={() => setFilterVisible(true)}
            accessibilityLabel="Filter places"
            accessibilityRole="button"
          >
            <Ionicons name="options-outline" size={20} color={hasActiveFilters(filters) ? Colors.primary : Colors.text} />
          </TouchableOpacity>
        )}
      </View>

      {mapLoading && (
        <View style={styles.mapBanner}>
          <ActivityIndicator size="small" color={Colors.primary} />
        </View>
      )}

      {mapError && features.length === 0 && (
        <TouchableOpacity
          style={styles.mapBanner}
          onPress={handleRetryMap}
          accessibilityRole="button"
          accessibilityLabel="Retry loading places"
        >
          <Text style={styles.mapBannerText}>Could not load places — tap to retry</Text>
        </TouchableOpacity>
      )}

      {mapLoaded && !mapLoading && features.length === 0 && (
        <View style={styles.mapBanner}>
          <Text style={styles.mapBannerText}>
            {viewMode === 'saved' ? "You haven't saved any places yet" : 'No places in this city yet'}
          </Text>
        </View>
      )}

      {mapLoaded && !mapLoading && features.length > 0 && filteredFeatures.length === 0 && (
        <TouchableOpacity
          style={styles.mapBanner}
          onPress={() => setFilters(EMPTY_FILTERS)}
          accessibilityRole="button"
          accessibilityLabel="Clear filters"
        >
          <Text style={styles.mapBannerText}>No matches for these filters — tap to clear</Text>
        </TouchableOpacity>
      )}

      {user && (
        <TouchableOpacity
          style={[styles.savedToggleButton, viewMode === 'saved' && styles.savedToggleButtonActive]}
          onPress={() => {
            Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
            setViewMode((m) => (m === 'saved' ? 'city' : 'saved'));
          }}
          accessibilityLabel={viewMode === 'saved' ? 'Show all places' : 'Show my saved places'}
          accessibilityRole="button"
        >
          <Ionicons
            name={viewMode === 'saved' ? 'bookmark' : 'bookmark-outline'}
            size={20}
            color={viewMode === 'saved' ? Colors.background : Colors.text}
          />
        </TouchableOpacity>
      )}

      {userLocation && (
        <TouchableOpacity
          style={styles.recenterButton}
          onPress={handleRecenter}
          accessibilityLabel="Recenter on my location"
          accessibilityRole="button"
        >
          <Ionicons name="locate" size={22} color={Colors.text} />
        </TouchableOpacity>
      )}

      <MapBottomSheet
        feature={selectedFeature}
        onOpen={(id) => {
          // The one real selection+navigation event for this surface --
          // see the module-level comment on why a bare pin tap alone
          // isn't separately logged. Position comes from the last
          // *logged* impression batch, not an arbitrary lookup, so a
          // click always ties back to a real "this was shown" event.
          const position = lastImpressionIdsRef.current.indexOf(id);
          logRecommendationEvent({
            surface: 'map',
            event_type: 'click',
            place_id: id,
            position: position >= 0 ? position : null,
            city_id: selectedCity?.id ?? null,
            search_session_id: mapSessionIdRef.current,
          });
          router.push(`/place/${id}`);
        }}
        onClose={() => setSelectedFeature(null)}
      />

      <FilterSheet
        visible={filterVisible}
        onClose={() => setFilterVisible(false)}
        filters={filters}
        onChange={setFilters}
        availableCategories={availableCategories}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  map: { flex: 1 },
  cityStrip: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.background + 'EE',
  },
  cityStripScroll: { flex: 1 },
  filterBtn: { padding: Spacing.sm, minWidth: 44, minHeight: 44, alignItems: 'center', justifyContent: 'center' },
  mapBanner: {
    position: 'absolute',
    top: 60,
    alignSelf: 'center',
    backgroundColor: Colors.surface,
    borderRadius: Radius.pill,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  recenterButton: {
    position: 'absolute',
    right: Spacing.md,
    bottom: Spacing.xl,
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    ...Shadows.control,
  },
  savedToggleButton: {
    position: 'absolute',
    right: Spacing.md,
    bottom: Spacing.xl + 56,
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    ...Shadows.control,
  },
  savedToggleButtonActive: {
    backgroundColor: Colors.primary,
    borderColor: Colors.primary,
  },
  mapBannerText: {
    color: Colors.textSecondary,
    fontSize: 13,
    fontWeight: '600',
  },
});
