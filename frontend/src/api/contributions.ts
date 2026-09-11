import { client } from './client';

export type ContributionIntent = 'private_log' | 'social_post';
export type ContributionReaction = 'loved' | 'good' | 'not_for_me';
export type ContributionVisibility = 'private' | 'connections' | 'public';

export interface ContributionCreate {
  client_id: string;
  place_id: string;
  intent: ContributionIntent;
  reaction?: ContributionReaction | null;
  caption?: string | null;
  visibility: ContributionVisibility;
  occurred_at?: string | null;
  image_id?: string | null;
  video_id?: string | null;
}

export interface ContributionOut extends ContributionCreate {
  id: string;
  status: 'committed' | 'deleted';
  created_at: string;
  updated_at: string;
}

export async function createContribution(payload: ContributionCreate): Promise<ContributionOut> {
  const { data } = await client.post<ContributionOut>('/api/v1/contributions', payload);
  return data;
}

export async function getContribution(id: string): Promise<ContributionOut> {
  const { data } = await client.get<ContributionOut>(`/api/v1/contributions/${id}`);
  return data;
}

export async function deleteContribution(id: string): Promise<void> {
  await client.delete(`/api/v1/contributions/${id}`);
}
