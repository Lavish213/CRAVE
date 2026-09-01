import { client } from './client';
import { PlaceOut, PlacesResponse } from './places';
import { normalizePlaceOut } from './normalize';

// GET /saves returns PlaceOut plus this user's per-save memory (E2) --
// kept as its own type rather than widening PlaceOut itself, since
// visited/visited_at/notes are only ever meaningful for a save, not the
// generic Feed/Search/Map card shape. See
// docs/E2_E3_E10_PRODUCT_TRADEOFFS_2026-08-31.md.
export interface SavedPlace extends PlaceOut {
  visited: boolean;
  visited_at: string | null;
  notes: string | null;
}

function normalizeSavedPlace(raw: unknown): SavedPlace {
  const base = normalizePlaceOut(raw);
  const r = (raw ?? {}) as Record<string, unknown>;
  return {
    ...base,
    visited: Boolean(r.visited),
    visited_at: typeof r.visited_at === 'string' ? r.visited_at : null,
    notes: typeof r.notes === 'string' ? r.notes : null,
  };
}

export async function fetchSaves(userId: string): Promise<SavedPlace[]> {
  const { data } = await client.get<PlacesResponse>('/api/v1/saves', {
    params: { user_id: userId },
  });
  if (__DEV__) console.log('[API] SAVES_RAW', { count: data?.items?.length, total: data?.total });
  const items = Array.isArray(data?.items) ? data.items : [];
  const normalized = items.map(normalizeSavedPlace);
  if (__DEV__) console.log('[API] SAVES_NORMALIZED', { count: normalized.length });
  return normalized;
}

export async function createSave(userId: string, placeId: string): Promise<void> {
  if (__DEV__) console.log('[API] SAVE_CREATE', { userId, placeId });
  await client.post('/api/v1/saves', { user_id: userId, place_id: placeId });
}

export async function deleteSave(userId: string, placeId: string): Promise<void> {
  if (__DEV__) console.log('[API] SAVE_DELETE', { userId, placeId });
  await client.delete(`/api/v1/saves/${placeId}`, { params: { user_id: userId } });
}

export interface SaveMemoryUpdate {
  visited?: boolean;
  /** `null` explicitly clears notes; omit the key entirely to leave
   * existing notes untouched -- see the backend route's exclude_unset
   * PATCH semantics (app/api/v1/routes/saves.py). */
  notes?: string | null;
}

export interface SaveMemoryResult {
  visited: boolean;
  visited_at: string | null;
  notes: string | null;
}

export async function updateSaveMemory(
  placeId: string,
  updates: SaveMemoryUpdate,
): Promise<SaveMemoryResult> {
  if (__DEV__) console.log('[API] SAVE_MEMORY_UPDATE', { placeId, updates });
  const { data } = await client.patch(`/api/v1/saves/${placeId}/memory`, updates);
  return {
    visited: Boolean(data?.visited),
    visited_at: typeof data?.visited_at === 'string' ? data.visited_at : null,
    notes: typeof data?.notes === 'string' ? data.notes : null,
  };
}
