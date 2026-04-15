// src/api/crave.ts
import { client } from './client';

export interface CraveItem {
  id: string;
  url: string;
  source_type: string;
  parsed_place_name: string | null;
  matched_place_id: string | null;
  match_confidence: number | null;
  status: string;
  created_at: string;
}

export async function getCraveItems(): Promise<CraveItem[]> {
  const { data } = await client.get<CraveItem[]>('/api/v1/craves');
  return data;
}
