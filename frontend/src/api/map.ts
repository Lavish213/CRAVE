import { client } from './client';
import { NormalizedMapFeature, normalizeMapFeatures } from './normalize';

export type { NormalizedMapFeature };

export async function fetchMapGeoJSON(params: {
  city_id?: string;
  lat: number;
  lng: number;
  radius_km?: number;
  category_id?: string;
  /** Backend already supports up to MAX_LIMIT (1000); omitted here uses
   * its own default (250). See MapScreenCore's widen-on-filter effect. */
  limit?: number;
}, signal?: AbortSignal): Promise<NormalizedMapFeature[]> {
  const { data } = await client.get('/api/v1/map/geojson', {
    params,
    ...(signal ? { signal } : {}),
  });
  if (!Array.isArray(data) && !Array.isArray((data as { features?: unknown[] } | null)?.features)) {
    throw new Error('Invalid map response: features must be an array.');
  }
  if (__DEV__) console.log('[API] MAP_RAW', { type: (data as any)?.type, feature_count: (data as any)?.features?.length, sample_coords: (data as any)?.features?.[0]?.geometry?.coordinates });
  const features = normalizeMapFeatures(data);
  if (__DEV__) console.log('[API] MAP_NORMALIZED', { count: features.length, sample: features[0] ? { id: features[0].id, lat: features[0].coordinate.lat, lng: features[0].coordinate.lng, tier: features[0].tier } : null });
  return features;
}

// The "my places" Map tab layer — your own saved places, not the global
// catalog. Unlike fetchMapGeoJSON, never viewport-scoped: a personal
// saved list is small, so the whole thing comes back at once and the
// map fits its bounds to it. Requires sign-in.
export async function fetchSavedPlacesGeoJSON(signal?: AbortSignal): Promise<NormalizedMapFeature[]> {
  const { data } = await client.get('/api/v1/saves/map', signal ? { signal } : undefined);
  if (!Array.isArray(data) && !Array.isArray((data as { features?: unknown[] } | null)?.features)) {
    throw new Error('Invalid saved-map response: features must be an array.');
  }
  const features = normalizeMapFeatures(data);
  if (__DEV__) console.log('[API] SAVED_MAP_NORMALIZED', { count: features.length });
  return features;
}
