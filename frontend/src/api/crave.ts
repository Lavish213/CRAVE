// src/api/crave.ts
//
// The share-to-CRAVE pipeline: submit a TikTok/YouTube/Instagram/web link
// mentioning a restaurant, the backend's share_parser_worker matches it to
// a Place (or feeds it into the discovery-candidate pipeline if unmatched —
// see backend/app/workers/share_parser_worker.py).
import { client } from './client';
import { normalizePlaceOut } from './normalize';
import type { DecisionSessionResponse } from './decisionSession';

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

// The no-link counterpart to submitShare — "I know the name of a place, I
// just don't have a video/post about it." Hits the backend's /hitlist/save
// endpoint (an older internal module name; the user-facing feature is still
// just Craves) which feeds the same discovery-candidate pipeline as
// everything else. lat/lng are optional but meaningfully raise confidence
// when present — pass the device's last-known location if you have it.
export interface PlaceSaveItem {
  id: string;
  place_name: string;
  source_platform: string | null;
  source_url: string | null;
  place_id: string | null;
  lat: number | null;
  lng: number | null;
  resolution_status: string;
  created_at: string | null;
  resolved_at: string | null;
}

export async function submitPlaceSave(
  placeName: string,
  opts?: { sourceUrl?: string; lat?: number; lng?: number },
): Promise<{ status: string; id: string; dedup_key: string }> {
  const { data } = await client.post('/api/v1/hitlist/save', {
    place_name: placeName.trim(),
    source_url: opts?.sourceUrl,
    lat: opts?.lat,
    lng: opts?.lng,
  });
  return data;
}

export async function getMyPlaceSaves(): Promise<PlaceSaveItem[]> {
  const { data } = await client.get<{ items: PlaceSaveItem[]; total: number }>('/api/v1/hitlist/me');
  return Array.isArray(data?.items) ? data.items : [];
}

// The no-coordinates counterpart to submitPlaceSave -- "I know the name
// and roughly the city, but not exactly where" (recalling a place from a
// trip, hearing about one secondhand). Distinct backend table
// (HitlistSuggestion, not HitlistSave) and a slightly lower starting
// confidence (0.4 vs 0.45) -- see backend/app/services/hitlist/
// suggest_intake.py. Both feed the same DiscoveryCandidate corroboration
// pipeline as every other "someone thinks this place exists" signal (GPS
// confirmations, social shares): a genuinely new contributor's suggestion
// adds to that place's accumulated confidence rather than replacing it, so
// repeated independent suggestions of the same place are what eventually
// cross the auto-promotion threshold and turn it into a real, uploaded
// Place -- not a single person's submission alone. There is no read-back
// endpoint for suggestions (HitlistSuggestion is intentionally
// write-only, unlike HitlistSave), so this is fire-and-forget by design.
export interface PlaceSuggestResponse {
  id: string;
  place_name: string;
  source_platform: string | null;
  created_at: string | null;
}

export async function suggestPlace(
  placeName: string,
  cityHint?: string,
): Promise<PlaceSuggestResponse> {
  const { data } = await client.post<PlaceSuggestResponse>('/api/v1/hitlist/suggest', {
    place_name: placeName.trim(),
    city_hint: cityHint?.trim() || undefined,
  });
  return data;
}

/** Removes one "Added" list entry by its exact place_name (the backend's
 * delete key -- HitlistSave has no separate client-facing id for this). */
export async function deletePlaceSave(placeName: string): Promise<void> {
  await client.delete('/api/v1/hitlist/delete', { params: { place_name: placeName } });
}

/**
 * Craves Screen Contract §5/§6's "reasoned subset" -- the same
 * build_decision_session() engine as Decision Session, scoped to this
 * user's saved pool instead of a city/radius fetch. Reuses Decision
 * Session's exact role vocabulary (best_fit/safe_bet/wildcard): this is
 * the literal same computation over a different candidate set, not a
 * conceptually distinct surface the way Search's own vocabulary is.
 */
export async function fetchCravesReasoned(opts?: {
  lat?: number;
  lng?: number;
}): Promise<DecisionSessionResponse> {
  const { data } = await client.get<DecisionSessionResponse>('/api/v1/craves/reasoned', {
    params: { lat: opts?.lat, lng: opts?.lng },
  });
  if (!Array.isArray(data?.cards)) {
    return { cards: [], degraded: true };
  }
  return {
    cards: data.cards.map((card) => ({
      ...card,
      place: normalizePlaceOut(card.place),
    })),
    degraded: Boolean(data.degraded),
  };
}
