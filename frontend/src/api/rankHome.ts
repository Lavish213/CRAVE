import { client } from './client';
import type { RankedPlace } from './social';

export type RankQueueEvidenceTier = 'declared' | 'verified';

export interface RankQueueItem {
  place_id: string;
  name: string;
  primary_image_url?: string | null;
  city_id?: string | null;
  visited_at: string;
  evidence_tier: RankQueueEvidenceTier;
  evidence_source: string;
}

export async function fetchRankQueue(limit = 30): Promise<RankQueueItem[]> {
  const { data } = await client.get<{ items?: RankQueueItem[] }>('/api/v1/rankings/queue', {
    params: { limit },
  });
  return Array.isArray(data?.items) ? data.items : [];
}

export interface RankHomeData {
  queue: RankQueueItem[];
  rankings: RankedPlace[];
}
