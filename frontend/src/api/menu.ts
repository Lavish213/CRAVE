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

export interface MenuItemSubmission {
  name: string;
  category?: string | null;
  /** Whole-dollar price as typed by the user — converted to cents here so
   * every caller doesn't have to remember the backend's unit. */
  price?: number | null;
  description?: string | null;
}

export interface MenuSubmissionResult {
  id: string;
  placeId: string;
  status: string;
  itemCount: number;
}

interface SubmitMenuResponse {
  id: string;
  place_id: string;
  status: string;
  item_count: number;
}

export async function submitMenu(
  placeId: string,
  items: MenuItemSubmission[],
): Promise<MenuSubmissionResult> {
  const payload = {
    items: items.map((item) => ({
      name: item.name,
      category: item.category ?? null,
      price_cents:
        item.price === null || item.price === undefined
          ? null
          : Math.round(item.price * 100),
      description: item.description ?? null,
    })),
  };

  const { data } = await client.post<SubmitMenuResponse>(
    `/api/v1/places/${placeId}/menu/submit`,
    payload,
  );

  return {
    id: data.id,
    placeId: data.place_id,
    status: data.status,
    itemCount: data.item_count,
  };
}
