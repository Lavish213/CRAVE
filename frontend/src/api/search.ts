import { client } from './client';
import { PlaceOut } from './places';
import { normalizePlaceOut } from './normalize';

interface SearchResponse {
  total: number;
  page: number;
  page_size: number;
  items: unknown[];
}

export async function searchPlaces(params: {
  query: string;
  city_id?: string;
  lat?: number;
  lng?: number;
  limit?: number;
}): Promise<PlaceOut[]> {
  const { data } = await client.get<SearchResponse>('/api/v1/search', { params });
  if (__DEV__) console.log('[API] SEARCH_RAW', { query: params.query, total: data?.total, count: data?.items?.length, sample: data?.items?.[0] });
  const items = Array.isArray(data?.items) ? data.items : [];
  const normalized = items.map(normalizePlaceOut);
  if (__DEV__) console.log('[API] SEARCH_NORMALIZED', { count: normalized.length, sample: normalized[0] ? { id: normalized[0].id, category: normalized[0].category, categories: normalized[0].categories } : null });
  return normalized;
}
