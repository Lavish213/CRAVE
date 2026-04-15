import { client } from './client';

export interface GeoJSONFeature {
  type: 'Feature';
  geometry: { type: 'Point'; coordinates: [number, number] };
  properties: {
    id: string;
    name: string;
    tier: 'elite' | 'trusted' | 'solid' | 'default';
    rank_score: number;
    price_tier: number | null;
    primary_image_url: string | null;
    has_menu: boolean;
  };
}

export interface GeoJSONFeatureCollection {
  type: 'FeatureCollection';
  features: GeoJSONFeature[];
}

export async function fetchMapGeoJSON(params: {
  city_id: string;
  category?: string;
}): Promise<GeoJSONFeatureCollection> {
  const { data } = await client.get<GeoJSONFeatureCollection>('/api/v1/map/geojson', { params });
  return data;
}
