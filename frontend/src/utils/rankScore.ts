// src/utils/rankScore.ts
//
// Presentation helpers for a user's personal ranking score. The backend
// stores rank_score on a 0-10 scale confined to per-tier bands (see
// backend app/db/models/place_ranking.py TIER_SCORE_BANDS) — these turn
// that raw float into something worth showing on a profile.
import { Colors } from '../constants/colors';

export type RankTier = 'liked' | 'fine' | 'disliked';

export const TIER_LABELS: Record<RankTier, string> = {
  liked: 'Loved it',
  fine: 'It was fine',
  disliked: "Didn't like it",
};

/** The three choices, in the order they're offered when logging a visit. */
export const TIER_CHOICES: { tier: RankTier; label: string; icon: string }[] = [
  { tier: 'liked', label: 'Loved it', icon: 'heart' },
  { tier: 'fine', label: 'It was fine', icon: 'remove-circle' },
  { tier: 'disliked', label: "Didn't like it", icon: 'thumbs-down' },
];

export function tierColor(tier: RankTier): string {
  if (tier === 'liked') return Colors.success;
  if (tier === 'fine') return Colors.warning;
  return Colors.textMuted;
}

/** One decimal is the resolution people expect from a 0-10 score. */
export function formatScore(score: number): string {
  return score.toFixed(1);
}

/**
 * Binary insertion over N existing places takes ceil(log2(N+1)) comparisons,
 * so the flow can honestly tell someone how many taps are left instead of
 * making an unbounded-feeling loop. Bounded low so "1 more" never renders as
 * "0 more" mid-flow.
 */
export function estimateComparisons(listSize: number): number {
  if (listSize <= 0) return 0;
  return Math.max(1, Math.ceil(Math.log2(listSize + 1)));
}

/**
 * Spotify-Wrapped framing: a bare count ("42 places") is a database row, an
 * identity line is what someone screenshots. Deliberately reads as a
 * statement about the person, not about the data.
 */
export function rankedListHeadline(count: number): string {
  if (count === 0) return 'Your list starts here';
  if (count === 1) return 'One place ranked. The list begins.';
  if (count < 5) return `${count} places ranked — you're building a taste`;
  if (count < 15) return `${count} places ranked and counting`;
  if (count < 50) return `${count} places ranked. You know this city.`;
  return `${count} places ranked. You *are* the guide.`;
}

/**
 * Beli gates recommendations until a user has ranked enough places for the
 * signal to mean anything — same threshold used here to decide whether to
 * nudge someone toward ranking more.
 */
export const RECOMMENDATION_THRESHOLD = 15;

export function recommendationProgress(count: number): {
  unlocked: boolean;
  remaining: number;
} {
  return {
    unlocked: count >= RECOMMENDATION_THRESHOLD,
    remaining: Math.max(0, RECOMMENDATION_THRESHOLD - count),
  };
}
