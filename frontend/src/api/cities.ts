import { client } from './client';

export interface CityOut {
  id: string;
  name: string;
  slug: string | null;
  lat: number | null;
  lng: number | null;
}

export async function fetchCities(): Promise<CityOut[]> {
  const { data } = await client.get<CityOut[]>('/api/v1/cities');
  return data;
}
