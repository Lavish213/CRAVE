// src/api/crave.ts
//
// The share-to-CRAVE pipeline: submit a TikTok/YouTube/Instagram/web link
// mentioning a restaurant, the backend's share_parser_worker matches it to
// a Place (or feeds it into the discovery-candidate pipeline if unmatched —
// see backend/app/workers/share_parser_worker.py).
import { client } from './client';

export type SourceType = 'instagram' | 'tiktok' | 'youtube' | 'twitter' | 'web' | 'other';

export interface CraveItem {
  id: string;
  url: string;
  source_type: string;
  parsed_place_name: string | null;
  matched_place_id: string | null;
  match_confidence: number | null;
  status: string;
  created_at: string;
  thumbnail_url: string | null;
  author_name: string | null;
}

// GET /craves is now auth-scoped to the caller (previously returned every
// user's shares with no filtering at all — see backend/app/api/v1/routes/craves.py).
export async function getCraveItems(): Promise<CraveItem[]> {
  const { data } = await client.get<CraveItem[]>('/api/v1/craves');
  if (__DEV__) console.log('[API] CRAVES_RAW', { count: Array.isArray(data) ? data.length : 'NOT_ARRAY', sample: Array.isArray(data) ? data[0] : data });
  return Array.isArray(data) ? data : [];
}

// Public — matched shares for a given place, for the "seen on social" section
// on the place detail screen.
export async function getCravesForPlace(placeId: string): Promise<CraveItem[]> {
  const { data } = await client.get<CraveItem[]>(`/api/v1/craves/for-place/${placeId}`);
  return Array.isArray(data) ? data : [];
}

export interface ShareIntakeResponse {
  id: string;
  status: string;
  message: string;
}

// Detects platform from a pasted URL so the user doesn't have to pick one
// manually. Falls back to 'web' (e.g. a blog post or restaurant site).
export function detectSourceType(url: string): SourceType {
  const lower = url.toLowerCase();
  if (lower.includes('tiktok.com')) return 'tiktok';
  if (lower.includes('instagram.com')) return 'instagram';
  if (lower.includes('youtube.com') || lower.includes('youtu.be')) return 'youtube';
  if (lower.includes('twitter.com') || lower.includes('x.com')) return 'twitter';
  return 'web';
}

// The one and only entry point into the share pipeline. Requires sign-in —
// submitted_by is always set server-side from the verified session token.
export async function submitShare(url: string, sourceType?: SourceType): Promise<ShareIntakeResponse> {
  const { data } = await client.post<ShareIntakeResponse>('/api/v1/share', {
    url: url.trim(),
    source_type: sourceType ?? detectSourceType(url),
  });
  return data;
}
