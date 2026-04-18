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
}

export async function getPlaceMenu(placeId: string): Promise<MenuItem[]> {
  const { data } = await client.get<MenuResponse>(`/api/v1/places/${placeId}/menu`);
  return normalizeMenuItems(data);
}
