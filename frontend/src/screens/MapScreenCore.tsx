import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, StyleSheet, View, useWindowDimensions } from 'react-native';
import MapView, { Marker, type Region } from 'react-native-maps';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { fetchMapGeoJSON, fetchSavedPlacesGeoJSON, type NormalizedMapFeature } from '../../src/api/map';
import { useCityStore } from '../../src/stores/cityStore';
import { useAuthStore } from '../../src/stores/authStore';
import { useLocationStatus } from '../../src/hooks/useLocation';
import { CitySelectorStrip } from '../../src/components/CitySelectorStrip';
import { MapBottomSheet } from '../../src/components/MapBottomSheet';
import { logRecommendationEvent, logRecommendationEvents } from '../../src/utils/recommendationEventQueue';
import { FilterSheet, type FilterState, EMPTY_FILTERS, hasActiveFilters } from '../../src/components/FilterSheet';
import { useDiscoveryContextStore } from '../../src/stores/discoveryContextStore';
import { CraveMapPin } from '../../src/ui-v2/components';
import { CraveButton, CraveIconButton, CraveSurface, CraveText } from '../../src/ui-v2/primitives';
import { buildMapClusters, isCoordinateInsideRegion, type MapClusterPoint } from '../../src/ui-v2/map/mapClustering';
import { selectMapPresentationItems } from '../../src/ui-v2/map/mapPresentationPolicy';
import { uiColors, uiControl, uiElevation, uiRadius, uiSpace } from '../../src/ui-v2/tokens';

let mapSessionSequence = 0;
function makeMapSessionId(): string {
  mapSessionSequence += 1;
  return `map_${Date.now().toString(36)}_${mapSessionSequence.toString(36)}`;
}

const PREFETCH_RADIUS_MULTIPLIER = 1.6;
const CLUSTER_TAP_MIN_DELTA = 0.0004;

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

type MapViewMode = 'city' | 'saved' | 'search';

export default function MapScreen() {
  const { width: viewportWidth, height: viewportHeight } = useWindowDimensions();
  const router = useRouter();
  const selectedCity = useCityStore((state) => state.selectedCity);
  const locationState = useLocationStatus();
  const userLocation = locationState.coords;
  const user = useAuthStore((state) => state.user);
  const mapRef = useRef<MapView>(null);

  const searchMapHandoff = useDiscoveryContextStore((state) => state.searchMapHandoff);
  const clearSearchMapHandoff = useDiscoveryContextStore((state) => state.clearSearchMapHandoff);

  const [viewMode, setViewMode] = useState<MapViewMode>(searchMapHandoff ? 'search' : 'city');
  const [filterVisible, setFilterVisible] = useState(false);
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);
  const [features, setFeatures] = useState<NormalizedMapFeature[]>([]);
  const [featuresContextKey, setFeaturesContextKey] = useState<string | null>(null);
  const [selectedFeature, setSelectedFeature] = useState<SelectedFeature | null>(null);
  const [mapLoading, setMapLoading] = useState(false);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [mapError, setMapError] = useState(false);
  const [pendingSearchRegion, setPendingSearchRegion] = useState<Region | null>(null);

  const programmaticMoveRef = useRef(false);
  const hasHandledFirstRegionRef = useRef(false);
  const requestIdRef = useRef(0);
  const lastFetchCoverageRef = useRef<FetchCoverage | null>(null);
  const lastAttemptRef = useRef<FetchCoverage | null>(null);
  const mapSessionIdRef = useRef(makeMapSessionId());
  const exposedMapIdsRef = useRef<Set<string>>(new Set());
  const visiblePinIdsRef = useRef<string[]>([]);
  const isFirstSessionMintRef = useRef(true);

  const currentFeatureContextKey = viewMode === 'saved'
    ? `saved:${user?.id ?? 'signed-out'}`
    : viewMode === 'search'
      ? `search:${searchMapHandoff?.query ?? 'none'}:${searchMapHandoff?.scope ?? 'all'}`
      : `city:${selectedCity?.id ?? 'nearby'}`;

  const activeFeatures = featuresContextKey === currentFeatureContextKey ? features : [];
  const mapLat = selectedCity?.lat ?? userLocation?.lat ?? DEFAULT_REGION.latitude;
  const mapLng = selectedCity?.lng ?? userLocation?.lng ?? DEFAULT_REGION.longitude;
  const initialRegion = cityToRegion(mapLat, mapLng);
  const [mapRegion, setMapRegion] = useState<Region>(initialRegion);

  useEffect(() => {
    if (isFirstSessionMintRef.current) {
      isFirstSessionMintRef.current = false;
      return;
    }
    mapSessionIdRef.current = makeMapSessionId();
    exposedMapIdsRef.current.clear();
    visiblePinIdsRef.current = [];
  }, [currentFeatureContextKey]);

  const fitFeatures = useCallback((items: readonly NormalizedMapFeature[], animated: boolean) => {
    if (items.length === 0) return;
    const coordinates = items.map((feature) => ({
      latitude: feature.coordinate.lat,
      longitude: feature.coordinate.lng,
    }));

    programmaticMoveRef.current = true;
    if (coordinates.length === 1) {
      const nextRegion = cityToRegion(coordinates[0].latitude, coordinates[0].longitude);
      setMapRegion(nextRegion);
      mapRef.current?.animateToRegion(nextRegion, animated ? 350 : 0);
      return;
    }

    mapRef.current?.fitToCoordinates(coordinates, {
      edgePadding: { top: 116, right: 52, bottom: 180, left: 52 },
      animated,
    });
  }, []);

  const loadFeatures = useCallback((lat: number, lng: number, radiusKm: number) => {
    const requestId = ++requestIdRef.current;
    const requestContextKey = `city:${selectedCity?.id ?? 'nearby'}`;
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
        if (requestId !== requestIdRef.current) return;
        setFeatures(normalized);
        setFeaturesContextKey(requestContextKey);
        setMapLoaded(true);
        lastFetchCoverageRef.current = { lat, lng, radiusKm };
      })
      .catch(() => {
        if (requestId !== requestIdRef.current) return;
        setMapError(true);
      })
      .finally(() => {
        if (requestId !== requestIdRef.current) return;
        setMapLoading(false);
      });
  }, [selectedCity?.id]);

  const loadSavedPlaces = useCallback(() => {
    const requestId = ++requestIdRef.current;
    const requestContextKey = `saved:${user?.id ?? 'signed-out'}`;
    setMapError(false);
    setMapLoading(true);

    fetchSavedPlacesGeoJSON()
      .then((normalized) => {
        if (requestId !== requestIdRef.current) return;
        setFeatures(normalized);
        setFeaturesContextKey(requestContextKey);
        setMapLoaded(true);
        fitFeatures(normalized, true);
      })
      .catch(() => {
        if (requestId !== requestIdRef.current) return;
        setMapError(true);
      })
      .finally(() => {
        if (requestId !== requestIdRef.current) return;
        setMapLoading(false);
      });
  }, [fitFeatures, user?.id]);

  useEffect(() => {
    if (!searchMapHandoff) return;

    const mapped = searchMapHandoff.items.flatMap<NormalizedMapFeature>((place) => {
      if (place.lat == null || place.lng == null) return [];
      const tier: NormalizedMapFeature['tier'] = place.tier === 'crave_pick'
        ? 'elite'
        : place.tier === 'gem'
          ? 'trusted'
          : place.tier === 'solid'
            ? 'solid'
            : 'default';

      return [{
        id: place.id,
        name: place.name,
        coordinate: { lat: place.lat, lng: place.lng },
        tier,
        rank_score: place.rank_score,
        price_tier: place.price_tier,
        image: place.image,
        category: place.category,
        has_menu: place.has_menu,
        has_video: place.has_video,
      }];
    });

    requestIdRef.current += 1;
    setViewMode('search');
    setFeatures(mapped);
    setFeaturesContextKey(`search:${searchMapHandoff.query}:${searchMapHandoff.scope}`);
    setMapLoaded(true);
    setMapLoading(false);
    setMapError(false);
    setPendingSearchRegion(null);
    fitFeatures(mapped, true);
  }, [fitFeatures, searchMapHandoff]);

  useEffect(() => {
    if (viewMode !== 'city') return;
    if (!selectedCity && !userLocation) {
      setFeatures([]);
      setFeaturesContextKey(null);
      setMapLoaded(false);
      setMapLoading(false);
      return;
    }

    lastFetchCoverageRef.current = null;
    setPendingSearchRegion(null);
    setSelectedFeature(null);
    setFeatures([]);
    setFeaturesContextKey(null);
    setMapLoaded(false);
    loadFeatures(mapLat, mapLng, prefetchRadiusKmForRegion(cityToRegion(mapLat, mapLng)));
  }, [loadFeatures, mapLat, mapLng, selectedCity?.id, userLocation?.lat, userLocation?.lng, viewMode]);

  useEffect(() => {
    if (viewMode !== 'city') return;
    const nextRegion = cityToRegion(mapLat, mapLng);
    programmaticMoveRef.current = true;
    setMapRegion(nextRegion);
    mapRef.current?.animateToRegion(nextRegion, 350);
  }, [mapLat, mapLng, selectedCity?.id, viewMode]);

  useEffect(() => {
    if (viewMode !== 'saved') return;
    if (!user) {
      setViewMode('city');
      return;
    }
    setSelectedFeature(null);
    setFeatures([]);
    setFeaturesContextKey(null);
    setMapLoaded(false);
    loadSavedPlaces();
  }, [loadSavedPlaces, user, viewMode]);

  const handleMapReady = useCallback(() => {
    if (viewMode === 'search') {
      fitFeatures(activeFeatures, false);
      return;
    }
    const nextRegion = cityToRegion(mapLat, mapLng);
    programmaticMoveRef.current = true;
    setMapRegion(nextRegion);
    mapRef.current?.animateToRegion(nextRegion, 250);
  }, [activeFeatures, fitFeatures, mapLat, mapLng, viewMode]);

  const handleRegionChangeComplete = useCallback((region: Region) => {
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
    const visibleRadiusKm = coverageRadiusKmForRegion(region);
    if (isCoveredByPriorFetch(region.latitude, region.longitude, visibleRadiusKm, lastFetchCoverageRef.current)) {
      setPendingSearchRegion(null);
      return;
    }

    setPendingSearchRegion(region);
  }, [viewMode]);

  const availableCategories = useMemo(() => {
    const names = new Set<string>();
    activeFeatures.forEach((feature) => {
      if (feature.category) names.add(feature.category);
    });
    return Array.from(names);
  }, [activeFeatures]);

  const filteredFeatures = useMemo(() => {
    if (!hasActiveFilters(filters)) return activeFeatures;
    return activeFeatures.filter((feature) => {
      if (
        filters.priceTiers.length > 0 &&
        (feature.price_tier == null || !filters.priceTiers.includes(feature.price_tier))
      ) {
        return false;
      }
      if (
        filters.categories.length > 0 &&
        (!feature.category || !filters.categories.includes(feature.category))
      ) {
        return false;
      }
      return true;
    });
  }, [activeFeatures, filters]);

  const presentationFeatures = useMemo(
    () => selectMapPresentationItems(filteredFeatures, { selectedId: selectedFeature?.id ?? null }),
    [filteredFeatures, selectedFeature?.id],
  );

  const clusters = useMemo(
    () => buildMapClusters(presentationFeatures, mapRegion, viewportWidth, viewportHeight),
    [mapRegion, presentationFeatures, viewportHeight, viewportWidth],
  );

  useEffect(() => {
    if (featuresContextKey !== currentFeatureContextKey || !mapLoaded || mapLoading || mapError) return;

    const visiblePins = clusters.filter(
      (cluster): cluster is MapClusterPoint & { feature: NormalizedMapFeature } =>
        cluster.count === 1 &&
        Boolean(cluster.feature) &&
        isCoordinateInsideRegion(cluster.latitude, cluster.longitude, mapRegion),
    );

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
        position: viewMode === 'search'
          ? searchMapHandoff?.items.findIndex((item) => item.id === cluster.feature.id) ?? null
          : visiblePinIdsRef.current.indexOf(cluster.feature.id),
        city_id: selectedCity?.id ?? null,
        query: viewMode === 'search' ? searchMapHandoff?.query : null,
        search_session_id: viewMode === 'search'
          ? searchMapHandoff?.searchSessionId ?? mapSessionIdRef.current
          : mapSessionIdRef.current,
      })),
    );
  }, [
    clusters,
    currentFeatureContextKey,
    featuresContextKey,
    mapError,
    mapLoaded,
    mapLoading,
    mapRegion,
    searchMapHandoff?.items,
    searchMapHandoff?.query,
    searchMapHandoff?.searchSessionId,
    selectedCity?.id,
    viewMode,
  ]);

  const handleRecenter = useCallback(() => {
    if (!userLocation) return;
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    const nextRegion = cityToRegion(userLocation.lat, userLocation.lng);
    programmaticMoveRef.current = true;
    setMapRegion(nextRegion);
    mapRef.current?.animateToRegion(nextRegion, 350);
  }, [userLocation]);

  const handleRetryMap = useCallback(() => {
    if (viewMode === 'search') return;
    if (viewMode === 'saved') {
      loadSavedPlaces();
      return;
    }
    const attempt = lastAttemptRef.current;
    if (attempt) {
      loadFeatures(attempt.lat, attempt.lng, attempt.radiusKm);
      return;
    }
    loadFeatures(mapLat, mapLng, prefetchRadiusKmForRegion(cityToRegion(mapLat, mapLng)));
  }, [loadFeatures, loadSavedPlaces, mapLat, mapLng, viewMode]);

  const handleSearchThisArea = useCallback(() => {
    if (!pendingSearchRegion) return;
    const region = pendingSearchRegion;
    setPendingSearchRegion(null);
    setSelectedFeature(null);
    loadFeatures(region.latitude, region.longitude, prefetchRadiusKmForRegion(region));
  }, [loadFeatures, pendingSearchRegion]);

  const handleExitSearch = useCallback(() => {
    clearSearchMapHandoff();
    setSelectedFeature(null);
    setViewMode('city');
  }, [clearSearchMapHandoff]);

  const handleToggleSaved = useCallback(() => {
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    clearSearchMapHandoff();
    setViewMode((mode) => (mode === 'saved' ? 'city' : 'saved'));
  }, [clearSearchMapHandoff]);

  const noLocation = viewMode === 'city' && !selectedCity && !userLocation && locationState.status !== 'resolving';
  const showEmpty = mapLoaded && featuresContextKey === currentFeatureContextKey && !mapLoading && !mapError && activeFeatures.length === 0;
  const showFilteredEmpty = mapLoaded && featuresContextKey === currentFeatureContextKey && !mapLoading && !mapError && activeFeatures.length > 0 && filteredFeatures.length === 0;

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
        {clusters.map((cluster) => {
          if (cluster.count > 1) {
            return (
              <Marker
                key={cluster.key}
                testID={`marker-cluster-${cluster.key}`}
                coordinate={{ latitude: cluster.latitude, longitude: cluster.longitude }}
                onPress={(event) => {
                  event.stopPropagation();
                  void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                  const zoomed: Region = {
                    latitude: cluster.latitude,
                    longitude: cluster.longitude,
                    latitudeDelta: Math.max(mapRegion.latitudeDelta / 2.5, CLUSTER_TAP_MIN_DELTA),
                    longitudeDelta: Math.max(mapRegion.longitudeDelta / 2.5, CLUSTER_TAP_MIN_DELTA),
                  };
                  programmaticMoveRef.current = true;
                  setMapRegion(zoomed);
                  mapRef.current?.animateToRegion(zoomed, 260);
                }}
                tracksViewChanges={false}
                accessibilityLabel={`${cluster.count} places`}
                accessibilityHint="Double tap to zoom in"
                accessibilityRole="button"
              >
                <CraveMapPin clusterCount={cluster.count} />
              </Marker>
            );
          }

          const feature = cluster.feature;
          if (!feature) return null;
          const selected = selectedFeature?.id === feature.id;
          return (
            <Marker
              key={cluster.key}
              testID={`marker-${feature.id}`}
              coordinate={{ latitude: feature.coordinate.lat, longitude: feature.coordinate.lng }}
              onPress={(event) => {
                event.stopPropagation();
                void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                setSelectedFeature({
                  id: feature.id,
                  name: feature.name,
                  tier: feature.tier,
                  image: feature.image ?? undefined,
                  category: feature.category ?? undefined,
                });
              }}
              tracksViewChanges={selected}
              accessibilityLabel={`${feature.name}${feature.category ? `, ${feature.category}` : ''}${selected ? ', selected' : ''}`}
              accessibilityHint="Opens a place preview"
              accessibilityRole="button"
            >
              <CraveMapPin label={feature.name} selected={selected} />
            </Marker>
          );
        })}
      </MapView>

      <View style={styles.topRail}>
        <View style={styles.citySelectorWrap}>
          <CitySelectorStrip />
        </View>
        {activeFeatures.length > 0 ? (
          <CraveIconButton
            icon={<Ionicons name="options-outline" size={20} color={hasActiveFilters(filters) ? uiColors.text.brand : uiColors.text.primary} />}
            onPress={() => setFilterVisible(true)}
            accessibilityLabel="Filter places"
            style={styles.topControl}
          />
        ) : null}
      </View>

      {viewMode === 'search' && searchMapHandoff ? (
        <CraveSurface tone="overlay" style={styles.contextPill}>
          <View style={styles.contextCopy}>
            <CraveText role="caption" tone="secondary" numberOfLines={1}>Search results</CraveText>
            <CraveText role="label" numberOfLines={1}>“{searchMapHandoff.query}”</CraveText>
          </View>
          <CraveButton label="Exit" variant="ghost" onPress={handleExitSearch} style={styles.compactButton} />
        </CraveSurface>
      ) : null}

      {viewMode === 'city' && pendingSearchRegion && !mapLoading ? (
        <CraveButton
          label="Search this area"
          variant="primary"
          onPress={handleSearchThisArea}
          style={styles.searchAreaButton}
        />
      ) : null}

      {mapLoading ? (
        <CraveSurface tone="overlay" style={styles.statusPill} accessibilityRole="text">
          <ActivityIndicator size="small" color={uiColors.accent.primaryAction} />
          <CraveText role="caption" tone="secondary">Updating places</CraveText>
        </CraveSurface>
      ) : null}

      {noLocation ? (
        <CraveSurface tone="overlay" style={styles.statusPill} accessibilityRole="text">
          <CraveText role="caption" tone="secondary">Choose an area to explore nearby places.</CraveText>
        </CraveSurface>
      ) : null}

      {mapError ? (
        <CraveSurface tone="overlay" style={styles.recoveryCard}>
          <CraveText role="caption" tone="secondary">
            {activeFeatures.length > 0 ? 'Showing the last loaded places.' : 'Places could not be loaded.'}
          </CraveText>
          <CraveButton label="Retry" variant="secondary" onPress={handleRetryMap} />
        </CraveSurface>
      ) : null}

      {showEmpty ? (
        <CraveSurface tone="overlay" style={styles.statusPill} accessibilityRole="text">
          <CraveText role="caption" tone="secondary">
            {viewMode === 'saved'
              ? "You haven't saved any places yet."
              : viewMode === 'search'
                ? 'No mapped places in these results.'
                : 'No places found in this area.'}
          </CraveText>
        </CraveSurface>
      ) : null}

      {showFilteredEmpty ? (
        <CraveSurface tone="overlay" style={styles.recoveryCard}>
          <CraveText role="caption" tone="secondary">No places match these refinements.</CraveText>
          <CraveButton label="Clear refinements" variant="secondary" onPress={() => setFilters(EMPTY_FILTERS)} />
        </CraveSurface>
      ) : null}

      <View style={styles.mapControls}>
        {user && viewMode !== 'search' ? (
          <CraveIconButton
            icon={<Ionicons name={viewMode === 'saved' ? 'bookmark' : 'bookmark-outline'} size={20} color={viewMode === 'saved' ? uiColors.text.brand : uiColors.text.primary} />}
            onPress={handleToggleSaved}
            accessibilityLabel={viewMode === 'saved' ? 'Show nearby places' : 'Show my saved places'}
            style={viewMode === 'saved' ? styles.selectedControl : undefined}
          />
        ) : null}
        {userLocation && viewMode === 'city' ? (
          <CraveIconButton
            icon={<Ionicons name="locate" size={21} color={uiColors.text.primary} />}
            onPress={handleRecenter}
            accessibilityLabel="Recenter on my location"
          />
        ) : null}
      </View>

      <MapBottomSheet
        feature={selectedFeature}
        onOpen={(id) => {
          const position = viewMode === 'search'
            ? searchMapHandoff?.items.findIndex((item) => item.id === id) ?? -1
            : visiblePinIdsRef.current.indexOf(id);
          logRecommendationEvent({
            surface: 'map',
            event_type: 'click',
            place_id: id,
            position: position >= 0 ? position : null,
            city_id: selectedCity?.id ?? null,
            query: viewMode === 'search' ? searchMapHandoff?.query : null,
            search_session_id: viewMode === 'search'
              ? searchMapHandoff?.searchSessionId ?? mapSessionIdRef.current
              : mapSessionIdRef.current,
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
  container: {
    flex: 1,
    backgroundColor: uiColors.surface.canvas,
  },
  map: {
    flex: 1,
  },
  topRail: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    flexDirection: 'row',
    alignItems: 'center',
    paddingRight: uiSpace.sm,
    backgroundColor: uiColors.surface.photoScrimStrong,
  },
  citySelectorWrap: {
    flex: 1,
  },
  topControl: {
    backgroundColor: uiColors.surface.overlay,
  },
  contextPill: {
    position: 'absolute',
    top: 64,
    left: uiSpace.md,
    right: uiSpace.md,
    minHeight: uiControl.minTarget,
    borderRadius: uiRadius.pill,
    paddingVertical: uiSpace.xs,
    paddingLeft: uiSpace.md,
    paddingRight: uiSpace.xs,
    flexDirection: 'row',
    alignItems: 'center',
    gap: uiSpace.sm,
    ...uiElevation.control,
  },
  contextCopy: {
    flex: 1,
    minWidth: 0,
  },
  compactButton: {
    minHeight: uiControl.minTarget,
    paddingHorizontal: uiSpace.sm,
  },
  searchAreaButton: {
    position: 'absolute',
    top: 72,
    alignSelf: 'center',
    borderRadius: uiRadius.pill,
    ...uiElevation.floating,
  },
  statusPill: {
    position: 'absolute',
    top: 72,
    alignSelf: 'center',
    maxWidth: '82%',
    minHeight: uiControl.minTarget,
    borderRadius: uiRadius.pill,
    paddingHorizontal: uiSpace.md,
    paddingVertical: uiSpace.sm,
    flexDirection: 'row',
    alignItems: 'center',
    gap: uiSpace.sm,
    ...uiElevation.control,
  },
  recoveryCard: {
    position: 'absolute',
    top: 72,
    left: uiSpace.lg,
    right: uiSpace.lg,
    borderRadius: uiRadius.card,
    padding: uiSpace.md,
    gap: uiSpace.sm,
    ...uiElevation.card,
  },
  mapControls: {
    position: 'absolute',
    right: uiSpace.md,
    bottom: 148,
    gap: uiSpace.sm,
  },
  selectedControl: {
    borderColor: uiColors.border.selected,
    backgroundColor: uiColors.surface.selected,
  },
});
