// src/api/social.ts
//
// Client for the profile / follow-graph / ranking / feed / leaderboard
// endpoints. All of these are user-scoped and rely on client.ts's
// interceptor attaching the Supabase bearer token — an unauthenticated
// call 401s rather than silently returning someone else's data.
import { client } from './client';

// ---------------------------------------------------------------------------
// Profile
// ---------------------------------------------------------------------------

export interface Profile {
  id: string;
  username: string;
  display_name: string | null;
  avatar_url: string | null;
  bio: string | null;
  is_public: boolean;
}

export async function checkUsernameAvailable(username: string): Promise<boolean> {
  const { data } = await client.get<{ available: boolean }>(
    '/api/v1/profile/username-available',
    { params: { username } },
  );
  return data.available;
}

export async function setupProfile(username: string, displayName?: string): Promise<Profile> {
  const { data } = await client.post<Profile>('/api/v1/profile/setup', {
    username,
    display_name: displayName ?? null,
  });
  return data;
}

/** Returns null when the signed-in user hasn't picked a username yet (404). */
export async function fetchMyProfile(): Promise<Profile | null> {
  try {
    const { data } = await client.get<Profile>('/api/v1/profile/me');
    return data;
  } catch (err: any) {
    if (err?.response?.status === 404) return null;
    throw err;
  }
}

export async function updateMyProfile(patch: {
  display_name?: string | null;
  bio?: string | null;
  avatar_url?: string | null;
  is_public?: boolean;
}): Promise<Profile> {
  const { data } = await client.patch<Profile>('/api/v1/profile/me', patch);
  return data;
}

// "Taste Profile" — the equivalent of Beli's own stats screen (total
// places ranked, tier breakdown, favorite cuisine, top city, a global
// percentile). Deliberately excludes Beli's "Match Score" (taste
// compatibility with a specific friend) — that's being built alongside
// the personalized-recommendations feature instead, which needs the
// same user-similarity computation.
export interface TasteProfile {
  total_ranked: number;
  tier_counts: { liked: number; fine: number; disliked: number };
  favorite_cuisine: string | null;
  top_city: { id: string; name: string; count: number } | null;
  percentile: number | null;
}

export async function fetchTasteProfile(userId: string): Promise<TasteProfile> {
  const { data } = await client.get<TasteProfile>(`/api/v1/profile/${userId}/taste`);
  return data;
}

export async function fetchProfile(userId: string): Promise<Profile> {
  const { data } = await client.get<Profile>(`/api/v1/profile/${userId}`);
  return data;
}

export async function requestAvatarUploadUrl(
  contentType: string,
): Promise<{ upload_url: string; public_url: string }> {
  const { data } = await client.post('/api/v1/profile/avatar/upload-url', {
    content_type: contentType,
  });
  return data;
}

// ---------------------------------------------------------------------------
// Follows
// ---------------------------------------------------------------------------

export async function followUser(userId: string): Promise<void> {
  await client.post(`/api/v1/follows/${userId}`);
}

export async function unfollowUser(userId: string): Promise<void> {
  await client.delete(`/api/v1/follows/${userId}`);
}

export async function fetchFollowStatus(
  userId: string,
): Promise<{ following: boolean; followed_by: boolean }> {
  const { data } = await client.get(`/api/v1/follows/status/${userId}`);
  return data;
}

export async function fetchFollowing(): Promise<string[]> {
  const { data } = await client.get<{ user_ids: string[] }>('/api/v1/follows/following');
  return data.user_ids ?? [];
}

export async function fetchFollowers(): Promise<string[]> {
  const { data } = await client.get<{ user_ids: string[] }>('/api/v1/follows/followers');
  return data.user_ids ?? [];
}

// ---------------------------------------------------------------------------
// Blocks
// ---------------------------------------------------------------------------

export async function blockUser(userId: string): Promise<void> {
  await client.post(`/api/v1/blocks/${userId}`);
}

export async function unblockUser(userId: string): Promise<void> {
  await client.delete(`/api/v1/blocks/${userId}`);
}

export async function fetchBlockStatus(userId: string): Promise<{ blocked: boolean }> {
  const { data } = await client.get(`/api/v1/blocks/status/${userId}`);
  return data;
}

export async function fetchBlockedUsers(): Promise<string[]> {
  const { data } = await client.get<{ user_ids: string[] }>('/api/v1/blocks');
  return data.user_ids ?? [];
}

// ---------------------------------------------------------------------------
// Account deletion
// ---------------------------------------------------------------------------

export async function deleteMyAccount(): Promise<{
  profile_deleted: boolean;
  supabase_account_deleted: boolean;
}> {
  const { data } = await client.delete('/api/v1/account/me', {
    data: { confirm: true },
  });
  return data;
}

// ---------------------------------------------------------------------------
// Rankings
// ---------------------------------------------------------------------------

/** Matches PlaceRanking's tiers — see backend app/db/models/place_ranking.py. */
export type RankTier = 'liked' | 'fine' | 'disliked';

export interface Ranking {
  place_id: string;
  tier: RankTier;
  rank_score: number;
  note: string | null;
  tags: string[] | null;
  visited_at: string | null;
}

// "X of your friends ranked this" — the direct equivalent of Beli's
// friend-rating feature. Separate call from the main place-detail fetch
// since that response is cached globally by place_id (shared across
// every viewer) — this one is per-viewer (scoped to the caller's own
// follow graph) and deliberately never cached, same pattern as
// getCravesForPlace's separate "seen on social" call.
export interface FriendRanking {
  user_id: string;
  username: string;
  display_name: string | null;
  avatar_url: string | null;
  tier: RankTier;
  rank_score: number;
}

export async function fetchFriendRankings(placeId: string): Promise<FriendRanking[]> {
  const { data } = await client.get<{ rankings: FriendRanking[]; count: number }>(
    `/api/v1/place/${placeId}/friends`,
  );
  return Array.isArray(data?.rankings) ? data.rankings : [];
}

/**
 * A ranking hydrated with enough of its place to render a list row without
 * a follow-up request per item. List endpoints return this; the ranking
 * flow's own result returns the bare `Ranking`.
 */
export interface RankedPlace extends Ranking {
  name: string | null;
  primary_image_url: string | null;
  city_id: string | null;
}

/**
 * Either the ranking finished immediately (first place in that tier — nothing
 * to compare against), or the backend wants a head-to-head answered before it
 * can place it. The caller drives the loop by POSTing the token back with a
 * winner until `status` comes back as 'ranked'.
 */
export type RankingStep =
  | { status: 'ranked'; ranking: Ranking }
  | { status: 'comparing'; comparison_token: string; opponent_place_id: string };

export async function startRanking(input: {
  place_id: string;
  tier: RankTier;
  visited_at?: string | null;
  note?: string | null;
  tags?: string[] | null;
}): Promise<RankingStep> {
  const { data } = await client.post<RankingStep>('/api/v1/rankings', input);
  return data;
}

export async function submitComparison(
  comparisonToken: string,
  winner: 'new' | 'opponent' | 'skip',
): Promise<RankingStep> {
  const { data } = await client.post<RankingStep>('/api/v1/rankings/compare', {
    comparison_token: comparisonToken,
    winner,
  });
  return data;
}

export async function fetchMyRankings(): Promise<RankedPlace[]> {
  const { data } = await client.get<{ rankings: RankedPlace[] }>('/api/v1/rankings/me');
  return data.rankings ?? [];
}

export async function fetchUserRankings(userId: string): Promise<RankedPlace[]> {
  const { data } = await client.get<{ rankings: RankedPlace[] }>(
    `/api/v1/rankings/user/${userId}`,
  );
  return data.rankings ?? [];
}

export async function deleteRanking(placeId: string): Promise<void> {
  await client.delete(`/api/v1/rankings/${placeId}`);
}

// ---------------------------------------------------------------------------
// Friends feed
// ---------------------------------------------------------------------------

/** Minimal identity shape the feed/leaderboard embed so rows are readable. */
export interface ActorRef {
  id: string;
  username: string | null;
  display_name: string | null;
  avatar_url: string | null;
}

export interface ActivityEvent {
  id: string;
  user_id: string;
  actor: ActorRef | null;
  event_type: 'ranked_place' | 'followed_user';
  place_id: string | null;
  place_name: string | null;
  place_image_url: string | null;
  target_user_id: string | null;
  target_user: ActorRef | null;
  payload: { tier?: RankTier; score?: number } | null;
  created_at: string;
}

export async function fetchFriendsFeed(limit = 30, offset = 0): Promise<ActivityEvent[]> {
  const { data } = await client.get<{ events: ActivityEvent[] }>('/api/v1/feed/friends', {
    params: { limit, offset },
  });
  return data.events ?? [];
}

// ---------------------------------------------------------------------------
// Leaderboard
// ---------------------------------------------------------------------------

export interface LeaderboardRow {
  user_id: string;
  places_logged: number;
  rank: number;
  username: string | null;
  display_name: string | null;
  avatar_url: string | null;
}

export async function fetchLeaderboard(opts: {
  among?: 'global' | 'friends';
  city_slug?: string | null;
  limit?: number;
} = {}): Promise<LeaderboardRow[]> {
  const { data } = await client.get<{ leaderboard: LeaderboardRow[] }>('/api/v1/leaderboard', {
    params: {
      among: opts.among ?? 'global',
      ...(opts.city_slug ? { city_slug: opts.city_slug } : {}),
      limit: opts.limit ?? 50,
    },
  });
  return data.leaderboard ?? [];
}

// ---------------------------------------------------------------------------
// Moderation (reporting)
// ---------------------------------------------------------------------------

export type ReportReason =
  | 'inappropriate'
  | 'not_this_place'
  | 'low_quality'
  | 'spam'
  | 'other';

export const REPORT_REASONS: { value: ReportReason; label: string }[] = [
  { value: 'inappropriate', label: 'Inappropriate or offensive' },
  { value: 'not_this_place', label: "Not this restaurant" },
  { value: 'low_quality', label: 'Bad photo quality' },
  { value: 'spam', label: 'Spam or advertising' },
  { value: 'other', label: 'Something else' },
];

/** Idempotent per user — reporting twice returns 'already_reported'. */
export async function reportImage(
  imageId: string,
  reason: ReportReason,
  note?: string,
): Promise<{ status: string; withheld?: boolean }> {
  const { data } = await client.post(`/api/v1/moderation/images/${imageId}/report`, {
    reason,
    note: note ?? null,
  });
  return data;
}
