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
  /** Approved + visible video exists for this place. Place Detail is
   * still the only playback surface -- this drives a discoverability
   * badge only. See docs/E2_E3_E10_PRODUCT_TRADEOFFS_2026-08-31.md (E3). */
  has_video: boolean;
  price_tier: number | null;
  /** Formatted price string, e.g. "$$$". Populated by normalizePlaceOut. */
  price?: string;
  /** Live open/closed, computed server-side from an OSM opening_hours tag
   * (see backend app/services/hours/opening_hours_service.py). null/absent
   * means genuinely unknown -- no OSM tag on file, or one the parser
   * couldn't read -- never a guessed or stale status. */
  hours_status?: 'open' | 'closed' | null;
  /** ISO timestamp of the next open<->closed transition. null/absent
   * whenever hours_status is null. */
  hours_next_change?: string | null;
  /** Raw OSM opening_hours string, for a "view hours" affordance. */
  hours_raw?: string | null;
  /** OSM's own outdoor_seating tag vocabulary. null/absent means no tag on
   * file -- never inferred or defaulted to "no". */
  outdoor_seating?: 'yes' | 'no' | 'limited' | null;
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

export interface PlaceRelationship {
  saved: boolean;
  visited: boolean;
  visited_at: string | null;
  notes: string | null;
  reason_role: string | null;
  reason_source: string | null;
  visit_confirmation_count: number;
  visit_evidence_tier: 'declared' | 'verified' | 'inferred' | null;
}

/**
 * Wave 7 -- Place Detail's relationship hierarchy. Deliberately a
 * separate call from fetchPlaceDetail: GET /place/{id} is cached
 * globally by place_id alone, so per-user data can't live in it (same
 * reasoning as the existing GET /place/{id}/friends call).
 */
export async function fetchPlaceRelationship(placeId: string): Promise<PlaceRelationship> {
  const { data } = await client.get<PlaceRelationship>(`/api/v1/place/${placeId}/relationship`);
  return data;
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
