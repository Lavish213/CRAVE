import { client } from './client';

export interface PlaceOut {
  id: string;
  name: string;
  city_id: string;
  rank_score: number;
  category: string | null;
  categories?: string[];
  address: string | null;
  lat: number | null;
  lng: number | null;
  primary_image_url: string | null;
  images?: string[];
  website: string | null;
  grubhub_url: string | null;
  has_menu: boolean;
  price_tier: number | null;
}

export interface PlacesResponse {
  total: number;
  page: number;
  page_size: number;
  items: PlaceOut[];
}

export async function fetchPlaces(params: {
  city_id: string;
  page?: number;
  page_size?: number;
}): Promise<PlacesResponse> {
  const { data } = await client.get<PlacesResponse>('/api/v1/places', { params });
  return data;
}

export async function fetchPlaceDetail(placeId: string): Promise<PlaceOut> {
  const { data } = await client.get<PlaceOut>(`/api/v1/place/${placeId}`);
  return data;
}

export async function fetchTrending(cityId: string): Promise<PlaceOut[]> {
  const { data } = await client.get<{ items: PlaceOut[] }>('/api/v1/trending', {
    params: { city_id: cityId },
  });
  return data.items;
}
