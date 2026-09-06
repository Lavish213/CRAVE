import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, TouchableOpacity, useWindowDimensions, View } from 'react-native';
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

// Recommendation Ledger, surface='map'. A fetched feature is a candidate,
// not an impression: the request deliberately covers 1.6x the visible
// viewport and filtering/clustering happen only after retrieval. An
// impression is therefore emitted only once a place is represented by an
// individual (non-clustered) pin inside the current viewport. Cluster
// children remain unexposed until zooming actually splits them into pins.
// No raw lat/lng/region is logged.
//
// The bottom-sheet "open" action remains the single click point. A bare pin
// tap is preview/engagement, not a full place-detail click, and a cluster tap
// has no single place_id to attribute.
function _makeMapSessionId(): string {
  return `map_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
}

const REGION_FETCH_DEBOUNCE_MS = 500;
const PREFETCH_RADIUS_MULTIPLIER = 1.6;
const STREET_CLUSTER_RADIUS = 44;
const NEIGHBORHOOD_CLUSTER_RADIUS = 56;
const CITY_CLUSTER_RADIUS_MIN = 64;
const CITY_CLUSTER_RADIUS_MAX = 84;
const CLUSTER_TAP_MIN_DELTA = 0.0004;

const TIER_COLORS: Record<string, string> = {
  elite: Colors.tierCravePick,
  trusted: Colors.tierGem,
  solid: Colors.tierSolid,
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

function radiusKmForRegion(region: Region): number {
  const latRad = (region.latitude * Math.PI) / 180;
  const kmPerLngDegree = 111.32 * Math.cos(latRad);
  const widthKm = region.longitudeDelta * kmPerLngDegree;
  const heightKm = region.latitudeDelta * 111.32;
  const radius = Math.max(widthKm, heightKm) / 2;
  return Math.min(50, Math.max(0.5, radius));
}

function prefetchRadiusKmForRegion(region: Region): number {
  return Math.min(50, radiusKmForRegion(region) * PREFETCH_RADIUS_MULTIPLIER);
}

function distanceKm(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const latRad = (((lat1 + lat2) / 2) * Math.PI) / 180;
  const kmPerLngDegree = 111.32 * Math.cos(latRad);
  const dLat = (lat2 - lat1) * 111.32;
  const dLng = (lng2 - lng1) * kmPerLngDegree;
  return Math.sqrt(dLat * dLat + dLng * dLng);
}

function coverageRadiusKmForRegion(region: Region): number {
  const latRad = (region.latitude * Math.PI) / 180;
  const widthKm = region.longitudeDelta * 111.32 * Math.cos(latRad);
  const heightKm = region.latitudeDelta * 111.32;
  return Math.hypot(widthKm, heightKm) / 2;
}

function isCoordinateVisibleInRegion(lat: number, lng: number, region: Region): boolean {
  const halfLat = region.latitudeDelta / 2;
  const halfLng = region.longitudeDelta / 2;
  return (
    lat >= region.latitude - halfLat &&
    lat <= region.latitude + halfLat &&
    lng >= region.longitude - halfLng &&
    lng <= region.longitude + halfLng
  );
}

interface FetchCoverage {
  lat: number;
  lng: number;
  radiusKm: number;
}

function isCoveredByPriorFetch(
  lat: number,
  lng: number,
  visibleRadiusKm: number,
  coverage: FetchCoverage | null,
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

export function buildClusters(
  features: NormalizedMapFeature[],
  region: Region,
  viewportWidth: number,
  viewportHeight: number,
): ClusterPoint[] {
  const densityBoost = Math.min(20, Math.max(0, features.length - 60) / 10);
  const radiusPx = region.longitudeDelta <= 0.005
    ? STREET_CLUSTER_RADIUS
    : region.longitudeDelta <= 0.02
      ? NEIGHBORHOOD_CLUSTER_RADIUS
      : Math.min(CITY_CLUSTER_RADIUS_MAX, CITY_CLUSTER_RADIUS_MIN + densityBoost);
  const safeWidth = Math.max(1, viewportWidth);
  const safeHeight = Math.max(1, viewportHeight);
  const west = region.longitude - region.longitudeDelta / 2;
  const north = region.latitude + region.latitudeDelta / 2;

  interface CollisionCluster {
    key: string;
    members: NormalizedMapFeature[];
    x: number;
    y: number;
    sumLat: number;
    sumLng: number;
  }

  const collisionClusters: CollisionCluster[] = [];
  for (const feature of features) {
    const x = ((feature.coordinate.lng - west) / region.longitudeDelta) * safeWidth;
    const y = ((north - feature.coordinate.lat) / region.latitudeDelta) * safeHeight;
    let nearest: CollisionCluster | undefined;
    let nearestDistance = Number.POSITIVE_INFINITY;

    for (const candidate of collisionClusters) {
      const distance = Math.hypot(candidate.x - x, candidate.y - y);
      if (distance < radiusPx && distance < nearestDistance) {
        nearest = candidate;
        nearestDistance = distance;
      }
    }

    if (!nearest) {
      collisionClusters.push({
        key: feature.id,
        members: [feature],
        x,
        y,
        sumLat: feature.coordinate.lat,
        sumLng: feature.coordinate.lng,
      });
      continue;
    }

    nearest.members.push(feature);
    nearest.sumLat += feature.coordinate.lat;
    nearest.sumLng += feature.coordinate.lng;
    nearest.x = nearest.members.reduce(
      (sum, member) => sum + ((member.coordinate.lng - west) / region.longitudeDelta) * safeWidth,
      0,
    ) / nearest.members.length;
    nearest.y = nearest.members.reduce(
      (sum, member) => sum + ((north - member.coordinate.lat) / region.latitudeDelta) * safeHeight,
      0,
    ) / nearest.members.length;
  }

  return collisionClusters.map((cluster) => {
    if (cluster.members.length === 1) {
      const feature = cluster.members[0];
      return {
        key: `point:${feature.id}`,
        latitude: feature.coordinate.lat,
        longitude: feature.coordinate.lng,
        count: 1,
        feature,
      };
    }
    return {
      key: `cluster:${cluster.key}`,
      latitude: cluster.sumLat / cluster.members.length,
      longitude: cluster.sumLng / cluster.members.length,
      count: cluster.members.length,
    };
  });
}

export default function MapScreen() {
  const { width: viewportWidth, height: viewportHeight } = useWindowDimensions();
  const router = useRouter();
  const selectedCity = useCityStore((s) => s.selectedCity);
  const userLocation = useLocation();
  const user = useAuthStore((s) => s.user);
  const mapRef = useRef<MapView>(null);

  const [viewMode, setViewMode] = useState<'city' | 'saved'>('city');
  const [filterVisible, setFilterVisible] = useState(false);
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);
  const programmaticMoveRef = useRef(false);
  const fetchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hasHandledFirstRegionRef = useRef(false);

  const [features, setFeatures] = useState<NormalizedMapFeature[]>([]);
  const [selectedFeature, setSelectedFeature] = useState<SelectedFeature | null>(null);
  const [mapLoading, setMapLoading] = useState(false);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [mapError, setMapError] = useState(false);

  const requestIdRef = useRef(0);
  const lastFetchCoverageRef = useRef<FetchCoverage | null>(null);

  const mapSessionIdRef = useRef(_makeMapSessionId());
  const exposedMapIdsRef = useRef<Set<string>>(new Set());
  const visiblePinIdsRef = useRef<string[]>([]);
  // Identifies which map session owns the currently loaded feature array.
  // On a city/mode transition, old pins can remain in React state until the
  // clearing effect commits; this prevents that old array from being logged
  // under the newly minted session during the transition render.
  const featuresSessionIdRef = useRef<string | null>(null);

  const isFirstSessionMintRef = useRef(true);
  useEffect(() => {
    if (isFirstSessionMintRef.current) {
      isFirstSessionMintRef.current = false;
      return;
    }
    mapSessionIdRef.current = _makeMapSessionId();
    exposedMapIdsRef.current = new Set();
    visiblePinIdsRef.current = [];
    featuresSessionIdRef.current = null;
  }, [selectedCity?.id, viewMode]);

  const mapLat = selectedCity?.lat ?? userLocation?.lat ?? DEFAULT_REGION.latitude;
  const mapLng = selectedCity?.lng ?? userLocation?.lng ?? DEFAULT_REGION.longitude;
  const initialRegion = cityToRegion(mapLat, mapLng);
  const [mapRegion, setMapRegion] = useState<Region>(initialRegion);
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
          if (__DEV__) {
            console.log('[MAP] FEATURES_LOADED', {
              count: normalized.length,
              lat,
              lng,
              radiusKm,
              cityId: selectedCity?.id,
              sample: normalized[0]
                ? {
                    id: normalized[0].id,
                    lat: normalized[0].coordinate.lat,
                    lng: normalized[0].coordinate.lng,
                    tier: normalized[0].tier,
                  }
                : null,
            });
          }
          featuresSessionIdRef.current = mapSessionIdRef.current;
          setFeatures(normalized);
          setMapLoaded(true);
          lastFetchCoverageRef.current = { lat, lng, radiusKm };
        })
        .catch((err: unknown) => {
          if (myRequestId !== requestIdRef.current) return;
          if (__DEV__) {
            const status = typeof err === 'object' && err !== null && 'response' in err
              ? (err as { response?: { status?: number; data?: unknown } }).response?.status
              : undefined;
            console.log('[MAP] LOAD_FAILED', {
              lat,
              lng,
              radiusKm,
              status,
              message: err instanceof Error ? err.message : String(err),
            });
          }
          setMapError(true);
        })
        .finally(() => {
          if (myRequestId !== requestIdRef.current) return;
          setMapLoading(false);
        });
    },
    [selectedCity?.id],
  );

  useEffect(() => {
    if (viewMode !== 'city') return;
    if (fetchDebounceRef.current) {
      clearTimeout(fetchDebounceRef.current);
      fetchDebounceRef.current = null;
    }
    lastFetchCoverageRef.current = null;
    featuresSessionIdRef.current = null;
    setFeatures([]);
    setMapLoaded(false);
    loadFeatures(mapLat, mapLng, prefetchRadiusKmForRegion(cityToRegion(mapLat, mapLng)));
  }, [selectedCity?.id, mapLat, mapLng, loadFeatures, viewMode]);

  useEffect(() => {
    if (viewMode !== 'city') return;
    const region = cityToRegion(mapLat, mapLng);
    programmaticMoveRef.current = true;
    setMapRegion(region);
    mapRef.current?.animateToRegion(region, 500);
  }, [selectedCity?.id, mapLat, mapLng, viewMode]);

  const loadSavedPlaces = useCallback(() => {
    const myRequestId = ++requestIdRef.current;
    setMapError(false);
    setMapLoading(true);
    fetchSavedPlacesGeoJSON()
      .then((normalized) => {
        if (myRequestId !== requestIdRef.current) return;
        if (__DEV__) console.log('[MAP] SAVED_FEATURES_LOADED', { count: normalized.length });
        featuresSessionIdRef.current = mapSessionIdRef.current;
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
      })
      .catch((err: unknown) => {
        if (myRequestId !== requestIdRef.current) return;
        if (__DEV__) {
          const status = typeof err === 'object' && err !== null && 'response' in err
            ? (err as { response?: { status?: number } }).response?.status
            : undefined;
          console.log('[MAP] SAVED_LOAD_FAILED', {
            message: err instanceof Error ? err.message : String(err),
            status,
          });
        }
        setMapError(true);
      })
      .finally(() => {
        if (myRequestId !== requestIdRef.current) return;
        setMapLoading(false);
      });
  }, []);

  useEffect(() => {
    if (viewMode !== 'saved') return;
    if (!user) {
      setViewMode('city');
      return;
    }
    featuresSessionIdRef.current = null;
    setFeatures([]);
    setMapLoaded(false);
    loadSavedPlaces();
  }, [viewMode, user, loadSavedPlaces]);

  const handleMapReady = useCallback(() => {
    const region = cityToRegion(mapLat, mapLng);
    programmaticMoveRef.current = true;
    setMapRegion(region);
    mapRef.current?.animateToRegion(region, 300);
  }, [mapLat, mapLng]);

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

      if (viewMode !== 'city') return;

      if (fetchDebounceRef.current) clearTimeout(fetchDebounceRef.current);
      fetchDebounceRef.current = setTimeout(() => {
        const visibleRadiusKm = coverageRadiusKmForRegion(region);
        if (
          isCoveredByPriorFetch(
            region.latitude,
            region.longitude,
            visibleRadiusKm,
            lastFetchCoverageRef.current,
          )
        ) {
          if (__DEV__) {
            console.log('[MAP] SKIP_FETCH_ALREADY_COVERED', {
              lat: region.latitude,
              lng: region.longitude,
              visibleRadiusKm,
            });
          }
          requestIdRef.current += 1;
          setMapLoading(false);
          setMapError(false);
          return;
        }
        loadFeatures(region.latitude, region.longitude, prefetchRadiusKmForRegion(region));
      }, REGION_FETCH_DEBOUNCE_MS);
    },
    [loadFeatures, viewMode],
  );

  const availableCategories = useMemo(() => {
    const names = new Set<string>();
    for (const f of features) {
      if (f.category) names.add(f.category);
    }
    return Array.from(names);
  }, [features]);

  const filteredFeatures = useMemo(() => {
    if (!hasActiveFilters(filters)) return features;
    return features.filter((f) => {
      if (
        filters.priceTiers.length > 0 &&
        (f.price_tier == null || !filters.priceTiers.includes(f.price_tier))
      ) return false;
      if (
        filters.categories.length > 0 &&
        (!f.category || !filters.categories.includes(f.category))
      ) return false;
      return true;
    });
  }, [features, filters]);

  const clusters = useMemo(
    () => buildClusters(filteredFeatures, mapRegion, viewportWidth, viewportHeight),
    [filteredFeatures, mapRegion, viewportWidth, viewportHeight],
  );

  // This is the Map equivalent of FlashList viewability: only a real
  // singleton marker whose coordinate lies in the current viewport counts as
  // exposed. The fetch's wider prefetch ring and all cluster children remain
  // candidates. Dedupe is scoped to one city/view-mode interaction session.
  useEffect(() => {
    if (featuresSessionIdRef.current !== mapSessionIdRef.current) {
      visiblePinIdsRef.current = [];
      return;
    }

    const visiblePins = clusters
      .filter((cluster): cluster is ClusterPoint & { feature: NormalizedMapFeature } => (
        cluster.count === 1 &&
        cluster.feature !== undefined &&
        isCoordinateVisibleInRegion(cluster.latitude, cluster.longitude, mapRegion)
      ));

    visiblePinIdsRef.current = visiblePins.map((cluster) => cluster.feature.id);
    const newlyExposed = visiblePins.filter(
      (cluster) => !exposedMapIdsRef.current.has(cluster.feature.id),
    );
    if (newlyExposed.length === 0) return;

    newlyExposed.forEach((cluster) => exposedMapIdsRef.current.add(cluster.feature.id));
    logRecommendationEvents(
      newlyExposed.map((cluster) => ({
        surface: 'map',
        event_type: 'impression',
        place_id: cluster.feature.id,
        position: visiblePinIdsRef.current.indexOf(cluster.feature.id),
        city_id: selectedCity?.id ?? null,
        search_session_id: mapSessionIdRef.current,
      })),
    );
  }, [clusters, mapRegion, selectedCity?.id]);

  const handleRecenter = useCallback(() => {
    if (!userLocation) return;
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    const region = cityToRegion(userLocation.lat, userLocation.lng);
    programmaticMoveRef.current = true;
    setMapRegion(region);
    mapRef.current?.animateToRegion(region, 500);
  }, [userLocation]);

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
                  e.stopPropagation();
                  void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
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
                accessibilityLabel={`Cluster of ${c.count} places. Double tap to zoom in.`}
                accessibilityRole="button"
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
                e.stopPropagation();
                void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                setSelectedFeature({
                  id: f.id,
                  name: f.name,
                  tier: f.tier,
                  image: f.image ?? undefined,
                  category: f.category ?? undefined,
                });
              }}
              tracksViewChanges={false}
              accessibilityLabel={`${f.name}${f.category ? `, ${f.category}` : ''}`}
              accessibilityHint="Opens a place preview"
              accessibilityRole="button"
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
            <Ionicons
              name="options-outline"
              size={20}
              color={hasActiveFilters(filters) ? Colors.primary : Colors.text}
            />
          </TouchableOpacity>
        )}
      </View>

      {mapLoading && (
        <View style={styles.mapBanner}>
          <ActivityIndicator size="small" color={Colors.primary} />
        </View>
      )}

      {mapError && (
        <TouchableOpacity
          style={styles.mapBanner}
          onPress={handleRetryMap}
          accessibilityRole="button"
          accessibilityLabel="Retry loading places"
        >
          <Text style={styles.mapBannerText}>
            {features.length > 0
              ? 'Showing previously loaded places — tap to retry'
              : 'Could not load places — tap to retry'}
          </Text>
        </TouchableOpacity>
      )}

      {mapLoaded && !mapLoading && !mapError && features.length === 0 && (
        <View style={styles.mapBanner}>
          <Text style={styles.mapBannerText}>
            {viewMode === 'saved' ? "You haven't saved any places yet" : 'No places in this city yet'}
          </Text>
        </View>
      )}

      {mapLoaded && !mapLoading && !mapError && features.length > 0 && filteredFeatures.length === 0 && (
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
            void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
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
          const position = visiblePinIdsRef.current.indexOf(id);
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
  filterBtn: {
    padding: Spacing.sm,
    minWidth: 44,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
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
