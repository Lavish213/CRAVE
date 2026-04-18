import { client } from './client';
import { PlaceOut, PlacesResponse } from './places';
import { normalizePlaceOut } from './normalize';

export async function fetchSaves(userId: string): Promise<PlaceOut[]> {
  const { data } = await client.get<PlacesResponse>('/api/v1/saves', {
    params: { user_id: userId },
  });
  if (__DEV__) console.log('[API] SAVES_RAW', { count: data?.items?.length, total: data?.total });
  const items = Array.isArray(data?.items) ? data.items : [];
  const normalized = items.map(normalizePlaceOut);
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
