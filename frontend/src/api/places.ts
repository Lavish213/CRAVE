import { client } from './client';
import { normalizePlaceOut } from './normalize';

export interface PlaceOut {
  id: string;
  name: string;
  city_id: string;
  rank_score: number;
  /** Backend-computed tier key. Mirrors scoring.ts getTier(). */
  tier: 'crave_pick' | 'gem' | 'solid' | 'new';
  /** This place's standing within its own city, in [0, 1] (1 = best in
   * the city). Null when no ranking snapshot exists for it yet -- callers
   * should fall back to absolute-score tiering. See getTier() below. */
  rank_percentile: number | null;
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
  /** Index-aligned with `images`. Needed to report a specific photo. */
  image_ids?: string[];
  /** Index-aligned with `images`. EXIF GPS on the photo matched the
   * place's own coordinates at upload time. */
  image_gps_verified?: boolean[];
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
  next_cursor?: string | null;
}

export async function fetchPlaces(params: {
  city_id?: string;
  lat?: number;
  lng?: number;
  radius_miles?: number;
  page?: number;
  page_size?: number;
  cursor?: string | null;
  pagination?: 'offset' | 'cursor';
}): Promise<PlacesResponse> {
  const { pagination = 'offset', ...query } = params;
  const endpoint = pagination === 'cursor' ? '/api/v1/places/feed' : '/api/v1/places';
  const { data } = await client.get<PlacesResponse>(endpoint, { params: query });
  if (__DEV__) console.log('[API] FEED_RAW', { total: data?.total, count: data?.items?.length, sample: data?.items?.[0] });
  const items = Array.isArray(data?.items) ? data.items.map(normalizePlaceOut) : [];
  if (__DEV__) console.log('[API] FEED_NORMALIZED', { count: items.length, sample: items[0] ? { id: items[0].id, category: items[0].category, categories: items[0].categories } : null });
  return {
    total: data?.total ?? 0,
    page: data?.page ?? 1,
    page_size: data?.page_size ?? 20,
    items,
    next_cursor: data?.next_cursor ?? null,
  };
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

// Personalized "For You" recommendations -- collaborative filtering over
// shared PlaceRanking rows (see backend recommendation_service.py).
// Requires auth; callers should only invoke this when a user is signed in.
export async function fetchRecommendations(limit = 20): Promise<PlaceOut[]> {
  const { data } = await client.get<{ items: PlaceOut[] }>('/api/v1/recommendations', {
    params: { limit },
  });
  const items = Array.isArray(data?.items) ? data.items : [];
  return items.map(normalizePlaceOut);
}
