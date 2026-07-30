import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import MapView, { Marker, Region } from 'react-native-maps';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { fetchMapGeoJSON, NormalizedMapFeature } from '../../src/api/map';
import { useCityStore } from '../../src/stores/cityStore';
import { useLocation } from '../../src/hooks/useLocation';
import { Colors, Radius, Spacing } from '../../src/constants/colors';
import { CitySelectorStrip } from '../../src/components/CitySelectorStrip';
import { MapMarkerDot, MapClusterDot } from '../../src/components/MapMarker';
import { MapBottomSheet } from '../../src/components/MapBottomSheet';

// How long to wait after the user stops panning/zooming before refetching —
// avoids firing a request on every intermediate frame of a gesture.
const REGION_FETCH_DEBOUNCE_MS = 500;

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

  // Effective center: city > user location > default
  const mapLat = selectedCity?.lat ?? userLocation?.lat ?? DEFAULT_REGION.latitude;
  const mapLng = selectedCity?.lng ?? userLocation?.lng ?? DEFAULT_REGION.longitude;

  const initialRegion = cityToRegion(mapLat, mapLng);
  const [mapRegion, setMapRegion] = useState<Region>(initialRegion);

  const loadFeatures = useCallback(
    (lat: number, lng: number, radiusKm: number) => {
      setMapError(false);
      setMapLoading(true);
      fetchMapGeoJSON({
        city_id: selectedCity?.id,
        lat,
        lng,
        radius_km: radiusKm,
      })
        .then((normalized) => {
          if (__DEV__) console.log('[MAP] FEATURES_LOADED', { count: normalized.length, radiusKm, sample: normalized[0] ? { id: normalized[0].id, lat: normalized[0].coordinate.lat, lng: normalized[0].coordinate.lng, tier: normalized[0].tier } : null });
          setFeatures(normalized);
          setMapLoaded(true);
        })
        .catch(() => setMapError(true))
        .finally(() => setMapLoading(false));
    },
    [selectedCity?.id]
  );

  // Initial load + reload on city change (or GPS location resolving).
  useEffect(() => {
    loadFeatures(mapLat, mapLng, radiusKmForRegion(cityToRegion(mapLat, mapLng)));
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
        loadFeatures(region.latitude, region.longitude, radiusKmForRegion(region));
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

      {mapError && (
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
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3,
    shadowRadius: 4,
    elevation: 4,
  },
  mapBannerText: {
    color: Colors.textSecondary,
    fontSize: 13,
    fontWeight: '600',
  },
});
