import React, { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import MapView, { Marker, Region } from 'react-native-maps';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { fetchMapGeoJSON, NormalizedMapFeature } from '../../src/api/map';
import { useCityStore } from '../../src/stores/cityStore';
import { useLocation } from '../../src/hooks/useLocation';
import { Colors, Radius, Spacing } from '../../src/constants/colors';
import { CitySelectorStrip } from '../../src/components/CitySelectorStrip';
import { MapMarkerDot } from '../../src/components/MapMarker';
import { MapBottomSheet } from '../../src/components/MapBottomSheet';

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

interface SelectedFeature {
  id: string;
  name: string;
  tier: string;
  image?: string;
  category?: string;
}

export default function MapScreen() {
  const router = useRouter();
  const selectedCity = useCityStore((s) => s.selectedCity);
  const userLocation = useLocation();
  const mapRef = useRef<MapView>(null);

  const [features, setFeatures] = useState<NormalizedMapFeature[]>([]);
  const [selectedFeature, setSelectedFeature] = useState<SelectedFeature | null>(null);
  const [mapLoading, setMapLoading] = useState(false);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [mapError, setMapError] = useState(false);

  // Effective center: city > user location > default
  const mapLat = selectedCity?.lat ?? userLocation?.lat ?? DEFAULT_REGION.latitude;
  const mapLng = selectedCity?.lng ?? userLocation?.lng ?? DEFAULT_REGION.longitude;

  useEffect(() => {
    setMapError(false);
    setMapLoaded(false);
    setMapLoading(true);
    fetchMapGeoJSON({
      city_id: selectedCity?.id,
      lat: mapLat,
      lng: mapLng,
    })
      .then((normalized) => {
        if (__DEV__) console.log('[MAP] FEATURES_LOADED', { count: normalized.length, sample: normalized[0] ? { id: normalized[0].id, lat: normalized[0].coordinate.lat, lng: normalized[0].coordinate.lng, tier: normalized[0].tier } : null });
        setFeatures(normalized);
        setMapLoaded(true);
      })
      .catch(() => setMapError(true))
      .finally(() => setMapLoading(false));
  }, [selectedCity?.id, mapLat, mapLng]);

  useEffect(() => {
    mapRef.current?.animateToRegion(cityToRegion(mapLat, mapLng), 500);
  }, [selectedCity?.id, mapLat, mapLng]);

  const initialRegion = cityToRegion(mapLat, mapLng);

  return (
    <View style={styles.container}>
      <MapView
        ref={mapRef}
        style={styles.map}
        initialRegion={initialRegion}
        mapType="mutedStandard"
        onPress={() => setSelectedFeature(null)}
      >
        {features.map((f) => {
          const color = TIER_COLORS[f.tier] ?? TIER_COLORS.default;
          return (
            <Marker
              key={f.id}
              coordinate={{ latitude: f.coordinate.lat, longitude: f.coordinate.lng }}
              onPress={() => {
                Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                setSelectedFeature({
                  id: f.id,
                  name: f.name,
                  tier: f.tier,
                  image: f.image ?? undefined,
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
  mapBannerText: {
    color: Colors.textSecondary,
    fontSize: 13,
    fontWeight: '600',
  },
});
