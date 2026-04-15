// app/(tabs)/map.tsx
import React, { useEffect, useRef, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import MapView, { Marker, Region } from 'react-native-maps';
import { useRouter } from 'expo-router';
import { fetchMapGeoJSON, GeoJSONFeature } from '../../src/api/map';
import { useCityStore } from '../../src/stores/cityStore';
import { Colors, Radius, Spacing } from '../../src/constants/colors';
import { CitySelectorStrip } from '../../src/components/CitySelectorStrip';
import { MapMarkerDot } from '../../src/components/MapMarker';
import { MapBottomSheet } from '../../src/components/MapBottomSheet';

// Map GeoJSON tier strings to canonical colors from colors.ts
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
  const mapRef = useRef<MapView>(null);

  const [features, setFeatures] = useState<GeoJSONFeature[]>([]);
  const [selectedFeature, setSelectedFeature] = useState<SelectedFeature | null>(null);
  const [mapError, setMapError] = useState(false);

  useEffect(() => {
    if (!selectedCity) return;
    setMapError(false);
    fetchMapGeoJSON({ city_id: selectedCity.id })
      .then((fc) => setFeatures(fc.features))
      .catch(() => setMapError(true));
  }, [selectedCity?.id]);

  useEffect(() => {
    if (!selectedCity?.lat || !selectedCity?.lng) return;
    mapRef.current?.animateToRegion(cityToRegion(selectedCity.lat, selectedCity.lng), 500);
  }, [selectedCity?.id]);

  const initialRegion =
    selectedCity?.lat && selectedCity?.lng
      ? cityToRegion(selectedCity.lat, selectedCity.lng)
      : DEFAULT_REGION;

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
          const [lng, lat] = f.geometry.coordinates;
          const tier = f.properties.tier as string;
          const color = TIER_COLORS[tier] ?? TIER_COLORS.default;
          return (
            <Marker
              key={f.properties.id}
              coordinate={{ latitude: lat, longitude: lng }}
              onPress={() => setSelectedFeature({
                id: f.properties.id,
                name: f.properties.name,
                tier,
                image: f.properties.primary_image_url ?? undefined,
                category: f.properties.category ?? undefined,
              })}
              tracksViewChanges={false}
            >
              <MapMarkerDot color={color} />
            </Marker>
          );
        })}
      </MapView>

      {/* City selector strip overlaid at top */}
      <View style={styles.cityStrip}>
        <CitySelectorStrip />
      </View>

      {/* Error banner — shown when GeoJSON fetch fails */}
      {mapError && (
        <View style={styles.mapErrorBanner}>
          <Text style={styles.mapErrorText}>Could not load places</Text>
        </View>
      )}

      {/* Bottom sheet on pin tap */}
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
  mapErrorBanner: {
    position: 'absolute',
    top: 60, // below the city strip
    alignSelf: 'center',
    backgroundColor: Colors.surface,
    borderRadius: Radius.pill,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  mapErrorText: {
    color: Colors.textSecondary,
    fontSize: 13,
    fontWeight: '600',
  },
});
