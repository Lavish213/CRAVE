import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import MapView, { Marker, Region } from 'react-native-maps';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { fetchMapGeoJSON, NormalizedMapFeature } from '../../src/api/map';
import { useCityStore } from '../../src/stores/cityStore';
import { useLocation } from '../../src/hooks/useLocation';
import { Colors, Radius, Shadows, Spacing } from '../../src/constants/colors';
import { CitySelectorStrip } from '../../src/components/CitySelectorStrip';
import { MapMarkerDot, MapClusterDot } from '../../src/components/MapMarker';
import { MapBottomSheet } from '../../src/components/MapBottomSheet';

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
const MIN_CLUSTER_SIZE = 3;
const MIN_CELL_SIZE_DEG = 0.0008;

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
  const mapRef = useRef<MapView>(null);

  // True for the one onRegionChangeComplete event caused by our own
  // animateToRegion call (city change / cluster tap) — lets us skip firing a
  // redundant viewport fetch for a move the user didn't make.
  const programmaticMoveRef = useRef(false);
  const fetchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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

  // Effective center: city > user location > default
  const mapLat = selectedCity?.lat ?? userLocation?.lat ?? DEFAULT_REGION.latitude;
  const mapLng = selectedCity?.lng ?? userLocation?.lng ?? DEFAULT_REGION.longitude;

  const initialRegion = cityToRegion(mapLat, mapLng);
  const [mapRegion, setMapRegion] = useState<Region>(initialRegion);

  const loadFeatures = useCallback(
    (lat: number, lng: number, radiusKm: number) => {
      const myRequestId = ++requestIdRef.current;
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
          if (__DEV__) console.log('[MAP] FEATURES_LOADED', { count: normalized.length, radiusKm, sample: normalized[0] ? { id: normalized[0].id, lat: normalized[0].coordinate.lat, lng: normalized[0].coordinate.lng, tier: normalized[0].tier } : null });
          setFeatures(normalized);
          setMapLoaded(true);
          lastFetchCoverageRef.current = { lat, lng, radiusKm };
        })
        .catch(() => {
          if (myRequestId !== requestIdRef.current) return;
          setMapError(true);
        })
        .finally(() => {
          if (myRequestId !== requestIdRef.current) return;
          setMapLoading(false);
        });
    },
    [selectedCity?.id]
  );

  // Initial load + reload on city change (or GPS location resolving).
  useEffect(() => {
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
  }, [selectedCity?.id, mapLat, mapLng, loadFeatures]);

  // Recenter the map on city change — flagged as programmatic so the
  // resulting onRegionChangeComplete doesn't trigger a duplicate fetch.
  useEffect(() => {
    const region = cityToRegion(mapLat, mapLng);
    programmaticMoveRef.current = true;
    setMapRegion(region);
    mapRef.current?.animateToRegion(region, 500);
  }, [selectedCity?.id, mapLat, mapLng]);

  // Clear any pending debounced fetch on unmount.
  useEffect(() => {
    return () => {
      if (fetchDebounceRef.current) clearTimeout(fetchDebounceRef.current);
    };
  }, []);

  const handleRegionChangeComplete = useCallback(
    (region: Region) => {
      setMapRegion(region);

      if (programmaticMoveRef.current) {
        programmaticMoveRef.current = false;
        return;
      }

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
    [loadFeatures]
  );

  const clusters = useMemo(() => buildClusters(features, mapRegion), [features, mapRegion]);

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

  return (
    <View style={styles.container}>
      <MapView
        ref={mapRef}
        style={styles.map}
        initialRegion={initialRegion}
        mapType="mutedStandard"
        onPress={() => setSelectedFeature(null)}
        onRegionChangeComplete={handleRegionChangeComplete}
      >
        {clusters.map((c) => {
          if (c.count > 1) {
            return (
              <Marker
                key={c.key}
                coordinate={{ latitude: c.latitude, longitude: c.longitude }}
                onPress={() => {
                  Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                  const zoomed: Region = {
                    latitude: c.latitude,
                    longitude: c.longitude,
                    latitudeDelta: Math.max(mapRegion.latitudeDelta / 2.5, 0.003),
                    longitudeDelta: Math.max(mapRegion.longitudeDelta / 2.5, 0.003),
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
              coordinate={{ latitude: f.coordinate.lat, longitude: f.coordinate.lng }}
              onPress={() => {
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
        <CitySelectorStrip />
      </View>

      {mapLoading && (
        <View style={styles.mapBanner}>
          <ActivityIndicator size="small" color={Colors.primary} />
        </View>
      )}

      {mapError && features.length === 0 && (
        <View style={styles.mapBanner}>
          <Text style={styles.mapBannerText}>Could not load places</Text>
        </View>
      )}

      {mapLoaded && !mapLoading && features.length === 0 && (
        <View style={styles.mapBanner}>
          <Text style={styles.mapBannerText}>No places in this city yet</Text>
        </View>
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
        onOpen={(id) => router.push(`/place/${id}`)}
        onClose={() => setSelectedFeature(null)}
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
    backgroundColor: Colors.background + 'EE',
  },
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
  mapBannerText: {
    color: Colors.textSecondary,
    fontSize: 13,
    fontWeight: '600',
  },
});
