import { client } from './client';
import { NormalizedMapFeature, normalizeMapFeatures } from './normalize';

export type { NormalizedMapFeature };

interface MapDebugPayload {
  type?: unknown;
  features?: Array<{
    geometry?: {
      coordinates?: unknown;
    };
  }>;
}

function toMapDebugPayload(value: unknown): MapDebugPayload | null {
  if (!value || typeof value !== 'object') return null;
  return value as MapDebugPayload;
}

export async function fetchMapGeoJSON(params: {
  city_id?: string;
  lat: number;
  lng: number;
  radius_km?: number;
  category_id?: string;
}): Promise<NormalizedMapFeature[]> {
  const { data } = await client.get('/api/v1/map/geojson', { params });
  if (__DEV__) {
    const debugPayload = toMapDebugPayload(data);
    console.log('[API] MAP_RAW', {
      type: debugPayload?.type,
      feature_count: debugPayload?.features?.length,
      sample_coords: debugPayload?.features?.[0]?.geometry?.coordinates,
    });
  }
  const features = normalizeMapFeatures(data);
  if (__DEV__) {
    console.log('[API] MAP_NORMALIZED', {
      count: features.length,
      sample: features[0]
        ? {
            id: features[0].id,
            lat: features[0].coordinate.lat,
            lng: features[0].coordinate.lng,
            tier: features[0].tier,
          }
        : null,
    });
  }
  return features;
}

// The "my places" Map tab layer — your own saved places, not the global
// catalog. Unlike fetchMapGeoJSON, never viewport-scoped: a personal
// saved list is small, so the whole thing comes back at once and the
// map fits its bounds to it. Requires sign-in.
export async function fetchSavedPlacesGeoJSON(): Promise<NormalizedMapFeature[]> {
  const { data } = await client.get('/api/v1/saves/map');
  const features = normalizeMapFeatures(data);
  if (__DEV__) console.log('[API] SAVED_MAP_NORMALIZED', { count: features.length });
  return features;
}
