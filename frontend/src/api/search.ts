import { client } from './client';
import { PlaceOut } from './places';
import { normalizePlaceOut } from './normalize';

interface SearchResponse {
  total: number;
  page: number;
  page_size: number;
  items: unknown[];
}

export async function searchPlaces(
  params: {
    query: string;
    city_id?: string;
    lat?: number;
    lng?: number;
    page_size?: number;
  },
  signal?: AbortSignal,
): Promise<PlaceOut[]> {
  // Forwarding React Query's own per-query AbortSignal here (search.tsx's
  // queryFn passes it through) means a query superseded by the next
  // keystroke's debounced fetch actually cancels the in-flight HTTP
  // request instead of just being ignored client-side once it resolves --
  // every keystroke was otherwise still running its full request to
  // completion over the network and against the backend, wasted work on
  // both ends for anything but the very last keystroke.
  const { data } = await client.get<SearchResponse>('/api/v1/search', { params, signal });
  if (__DEV__) console.log('[API] SEARCH_RAW', { query: params.query, total: data?.total, count: data?.items?.length, sample: data?.items?.[0] });
  const items = Array.isArray(data?.items) ? data.items : [];
  const normalized = items.map(normalizePlaceOut);
  if (__DEV__) console.log('[API] SEARCH_NORMALIZED', { count: normalized.length, sample: normalized[0] ? { id: normalized[0].id, category: normalized[0].category, categories: normalized[0].categories } : null });
  return normalized;
}
