import { client } from './client';
import { PlaceOut } from './places';

interface SearchResponse {
  total: number;
  page: number;
  page_size: number;
  items: Array<Omit<PlaceOut, 'primary_image_url'> & { primary_image?: string | null }>;
}

export async function searchPlaces(params: {
  query: string;
  city_id: string;
  limit?: number;
}): Promise<PlaceOut[]> {
  const { data } = await client.get<SearchResponse>('/api/v1/search', { params });
  const items = Array.isArray(data?.items) ? data.items : [];
  return items.map((item) => ({
    ...item,
    primary_image_url: item.primary_image ?? null,
  }));
}
