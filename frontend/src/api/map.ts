import { client } from './client';
import { NormalizedMapFeature, normalizeMapFeatures } from './normalize';

export type { NormalizedMapFeature };

export async function fetchMapGeoJSON(params: {
  city_id?: string;
  lat: number;
  lng: number;
  category?: string;
}): Promise<NormalizedMapFeature[]> {
  const { data } = await client.get('/api/v1/map/geojson', { params });
  if (__DEV__) console.log('[API] MAP_RAW', { type: (data as any)?.type, feature_count: (data as any)?.features?.length, sample_coords: (data as any)?.features?.[0]?.geometry?.coordinates });
  const features = normalizeMapFeatures(data);
  if (__DEV__) console.log('[API] MAP_NORMALIZED', { count: features.length, sample: features[0] ? { id: features[0].id, lat: features[0].coordinate.lat, lng: features[0].coordinate.lng, tier: features[0].tier } : null });
  return features;
}
