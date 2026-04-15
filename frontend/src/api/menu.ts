// src/api/menu.ts
import { client } from './client';

export interface MenuItem {
  id: string;
  name: string;
  description: string | null;
  price: number | null;
  category: string | null;
}

export async function getPlaceMenu(placeId: string): Promise<MenuItem[]> {
  const { data } = await client.get<MenuItem[]>(`/api/v1/places/${placeId}/menu`);
  return data;
}
