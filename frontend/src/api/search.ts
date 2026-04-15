// src/api/search.ts
import { client } from './client';
import { PlaceOut } from './places';

export async function searchPlaces(params: {
  q: string;
  city_id: string;
  limit?: number;
}): Promise<PlaceOut[]> {
  const { data } = await client.get<PlaceOut[]>('/api/v1/search', { params });
  return data;
}
