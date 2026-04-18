import { client } from './client';

export interface CategoryOut {
  id: string;
  name: string;
  icon: string | null;
  color: string | null;
}

export interface CategoriesResponse {
  total: number;
  items: CategoryOut[];
}

export async function fetchCategories(): Promise<CategoryOut[]> {
  const { data } = await client.get<CategoriesResponse>('/api/v1/categories');
  if (!Array.isArray(data?.items)) return [];
  return data.items.filter((c) => c.id && c.name);
}
