import { client } from './client';
import { PlaceOut } from './places';
import { normalizePlaceOut } from './normalize';

export interface SearchInterpretation {
  original_query: string;
  lookup_query: string;
  price_tier: number | null;
  required_categories: string[];
  hard_constraints: string[];
  unsupported_hard_constraints: string[];
  context: string[];
  uncertain: boolean;
}

interface SearchResponse {
  total: number;
  page: number;
  page_size: number;
  items: unknown[];
  interpretation: SearchInterpretation;
  exact_match_id: string | null;
  relaxed_constraints: string[];
}

export interface SearchResultSet {
  total: number;
  page: number;
  page_size: number;
  items: PlaceOut[];
  interpretation: SearchInterpretation;
  exact_match_id: string | null;
  relaxed_constraints: string[];
}

export async function searchPlaces(
  params: {
    query: string;
    city_id?: string;
    lat?: number;
    lng?: number;
    /** Excludes results beyond this distance. Backend ignores it unless
     * lat/lng are also present (see search.py's effective_radius_miles). */
    radius_miles?: number;
    page_size?: number;
  },
  signal?: AbortSignal,
): Promise<SearchResultSet> {
  // Forwarding React Query's own per-query AbortSignal here (search.tsx's
  // queryFn passes it through) means a query superseded by the next
  // keystroke's debounced fetch actually cancels the in-flight HTTP
  // request instead of just being ignored client-side once it resolves --
  // every keystroke was otherwise still running its full request to
  // completion over the network and against the backend, wasted work on
  // both ends for anything but the very last keystroke.
  const { data } = await client.get<SearchResponse>('/api/v1/search', { params, signal });
  if (__DEV__) console.log('[API] SEARCH_RAW', { query: params.query, total: data?.total, count: data?.items?.length, sample: data?.items?.[0] });
  if (!data || !Array.isArray(data.items)) {
    throw new Error('Invalid search response: items must be an array.');
  }
  const items = data.items;
  const normalized = items.map(normalizePlaceOut);
  const fallbackInterpretation: SearchInterpretation = {
    original_query: params.query,
    lookup_query: params.query,
    price_tier: null,
    required_categories: [],
    hard_constraints: [],
    unsupported_hard_constraints: [],
    context: [],
    uncertain: false,
  };
  if (__DEV__) console.log('[API] SEARCH_NORMALIZED', { count: normalized.length, sample: normalized[0] ? { id: normalized[0].id, category: normalized[0].category, categories: normalized[0].categories } : null });
  return {
    total: typeof data?.total === 'number' ? data.total : normalized.length,
    page: typeof data?.page === 'number' ? data.page : 1,
    page_size: typeof data?.page_size === 'number' ? data.page_size : normalized.length,
    items: normalized,
    // Keep a rolling frontend/backend deploy safe. A client updated before
    // the structured-response backend must still render ordinary results.
    interpretation: data?.interpretation ?? fallbackInterpretation,
    exact_match_id: data.exact_match_id ?? null,
    relaxed_constraints: Array.isArray(data.relaxed_constraints) ? data.relaxed_constraints : [],
  };
}
