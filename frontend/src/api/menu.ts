import { client } from './client';
import { normalizeMenuItems } from './normalize';

export interface MenuItem {
  id: string;
  name: string;
  description: string | null;
  price: number | null;
  category: string | null;
}

interface MenuResponse {
  items: MenuItem[];
  /** ISO timestamp of the last successful menu materialization, or null
   * if this place's menu has never been (re)verified. */
  last_verified_at?: string | null;
}

export interface PlaceMenu {
  items: MenuItem[];
  lastVerifiedAt: string | null;
}

export async function getPlaceMenu(placeId: string): Promise<PlaceMenu> {
  const { data } = await client.get<MenuResponse>(`/api/v1/places/${placeId}/menu`);
  return {
    items: normalizeMenuItems(data),
    lastVerifiedAt: data?.last_verified_at ?? null,
  };
}
