import { client } from './client';
import { normalizePlaceOut } from './normalize';

export interface PlaceOut {
  id: string;
  name: string;
  city_id: string;
  rank_score: number;
  /** Backend-computed tier key. Mirrors scoring.ts getTier(). */
  tier: 'crave_pick' | 'gem' | 'solid' | 'new';
  /** Backend-computed distance in miles. Present when lat/lng was sent. */
  distance_miles: number | null;
  category: string | null;
  categories: string[];
  address: string | null;
  lat: number | null;
  lng: number | null;
  image: string | null;
  primary_image_url: string | null;
  images: string[];
  website: string | null;
  grubhub_url: string | null;
  has_menu: boolean;
  price_tier: number | null;
  /** Formatted price string, e.g. "$$$". Populated by normalizePlaceOut. */
  price?: string;
}

export interface PlacesResponse {
  total: number;
  page: number;
  page_size: number;
  items: PlaceOut[];
}

export async function fetchPlaces(params: {
  city_id?: string;
  lat?: number;
  lng?: number;
  radius_miles?: number;
  page?: number;
  page_size?: number;
}): Promise<PlacesResponse> {
  const { data } = await client.get<PlacesResponse>('/api/v1/places', { params });
  if (__DEV__) console.log('[API] FEED_RAW', { total: data?.total, count: data?.items?.length, sample: data?.items?.[0] });
  const items = Array.isArray(data?.items) ? data.items.map(normalizePlaceOut) : [];
  if (__DEV__) console.log('[API] FEED_NORMALIZED', { count: items.length, sample: items[0] ? { id: items[0].id, category: items[0].category, categories: items[0].categories } : null });
  return { total: data?.total ?? 0, page: data?.page ?? 1, page_size: data?.page_size ?? 20, items };
}

export async function fetchPlaceDetail(placeId: string): Promise<PlaceOut> {
  const { data } = await client.get<PlaceOut>(`/api/v1/place/${placeId}`);
  if (__DEV__) console.log('[API] DETAIL_RAW', { id: (data as any)?.id, category: (data as any)?.category, categories: (data as any)?.categories, images: (data as any)?.images?.length });
  const normalized = normalizePlaceOut(data);
  if (__DEV__) console.log('[API] DETAIL_NORMALIZED', { id: normalized.id, category: normalized.category, lat: normalized.lat, lng: normalized.lng });
  return normalized;
}

export async function fetchTrending(cityId: string): Promise<PlaceOut[]> {
  const { data } = await client.get<{ items: PlaceOut[] }>('/api/v1/trending', {
    params: { city_id: cityId },
  });
  if (__DEV__) console.log('[API] TRENDING_RAW', { count: data?.items?.length });
  const items = Array.isArray(data?.items) ? data.items : [];
  return items.map(normalizePlaceOut);
}
