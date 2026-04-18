// src/utils/scoring.ts
import { PlaceOut } from '../api/places';
import { Colors } from '../constants/colors';

export type TierKey = 'crave_pick' | 'gem' | 'solid' | 'new';

export interface Tier {
  key: TierKey;
  label: string;
  color: string;
  sectionLabel: string;
  sectionSubtext: string;
}

export const TIERS: Record<TierKey, Tier> = {
  crave_pick: {
    key: 'crave_pick',
    label: 'CRAVE Pick',
    color: Colors.tierCravePick,
    sectionLabel: 'CRAVE Picks',
    sectionSubtext: 'Verified by the city. Worth the trip.',
  },
  gem: {
    key: 'gem',
    label: 'Hidden Gem',
    color: Colors.tierGem,
    sectionLabel: 'Hidden Gems',
    sectionSubtext: 'Off the grid. Only the city knows.',
  },
  solid: {
    key: 'solid',
    label: 'Worth Knowing',
    color: Colors.tierSolid,
    sectionLabel: 'Worth Knowing',
    sectionSubtext: 'Reliable, real, worth your time.',
  },
  new: {
    key: 'new',
    label: 'Explore',
    color: Colors.tierNew,
    sectionLabel: 'Explore',
    sectionSubtext: 'Early signal. Watch this space.',
  },
};

export function getTier(score: number): Tier {
  if (score >= 0.42) return TIERS.crave_pick;
  if (score >= 0.32) return TIERS.gem;
  if (score >= 0.22) return TIERS.solid;
  return TIERS.new;
}

// ─── Price inference ──────────────────────────────────────────────────────────

const PRICE_4_KEYWORDS = [
  'omakase', 'tasting menu', 'prix fixe', 'michelin', 'fine dining',
  'benu', 'atelier crenn', 'quince', 'saison', 'lazy bear', 'manresa',
  'providence', 'n/naka', 'vespertine', 'melisse',
];

const PRICE_3_KEYWORDS = [
  'steakhouse', 'steak house', 'chophouse', 'sushi bar', 'kappo',
  'izakaya', 'robata', 'kaiseki', 'wine bar', 'oyster bar',
  'rooftop', 'brasserie',
];

const PRICE_1_KEYWORDS = [
  'taco', 'truck', 'food truck', 'stand', 'counter', 'boba', 'bubble tea',
  'wing', 'wings', 'hot dog', 'falafel', 'shawarma', 'pupusa',
  'food court', 'cafeteria',
];

/**
 * Infer a price tier (1–4) from place name + category when price_tier is null.
 * Returns null when confidence is too low to infer.
 */
export function inferPrice(place: PlaceOut): number | null {
  if (place.price_tier != null) return place.price_tier;

  const haystack = [place.name, place.category, ...(place.categories ?? [])]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();

  if (PRICE_4_KEYWORDS.some((kw) => haystack.includes(kw))) return 4;
  if (PRICE_3_KEYWORDS.some((kw) => haystack.includes(kw))) return 3;
  if (PRICE_1_KEYWORDS.some((kw) => haystack.includes(kw))) return 1;

  return null;
}

/**
 * Format a price tier as dollar signs, or null if unknown.
 */
export function formatPrice(place: PlaceOut): string | null {
  const tier = inferPrice(place);
  if (tier == null) return null;
  return '$'.repeat(tier);
}

// ─── Badges (emoji chips) ────────────────────────────────────────────────────

export interface Badge {
  emoji: string;
  label: string;
}

/**
 * Returns 0–3 contextual emoji chips for a place card.
 * Order: quality signal → menu/order → access indicator.
 */
export function getBadges(place: PlaceOut): Badge[] {
  const badges: Badge[] = [];

  const tier = getTier(place.rank_score);

  if (tier.key === 'crave_pick') {
    badges.push({ emoji: '⭐', label: 'CRAVE Pick' });
  } else if (tier.key === 'gem') {
    badges.push({ emoji: '💎', label: 'Hidden Gem' });
  }

  if (place.has_menu && place.grubhub_url) {
    badges.push({ emoji: '🛵', label: 'Delivery' });
  } else if (place.has_menu) {
    badges.push({ emoji: '📋', label: 'Menu' });
  }

  if (!place.has_menu && !place.grubhub_url && !place.website) {
    badges.push({ emoji: '🗺️', label: 'Off the grid' });
  }

  return badges.slice(0, 3);
}

// ─── Legacy: kept for backward compat during migration ───────────────────────

export interface TrustBadge {
  label: string;
  color: string;
  bg: string;
}

/** @deprecated Use getBadges() instead */
export function getTrustBadges(place: PlaceOut): TrustBadge[] {
  const result: TrustBadge[] = [];
  const tier = getTier(place.rank_score);
  if (tier.key === 'crave_pick')
    result.push({ label: 'CRAVE Pick', color: Colors.tierCravePick, bg: '#FF4D0022' });
  if (tier.key === 'gem')
    result.push({ label: 'Hidden Gem', color: Colors.tierGem, bg: '#FFB80022' });
  if (place.has_menu)
    result.push({ label: 'Full menu', color: Colors.tierSolid, bg: '#4CAF5022' });
  if (place.grubhub_url)
    result.push({ label: 'Order online', color: Colors.textSecondary, bg: '#88888822' });
  if (place.website && !place.grubhub_url)
    result.push({ label: 'Dine in only', color: Colors.textSecondary, bg: '#88888822' });
  if (!place.has_menu && !place.grubhub_url && !place.website)
    result.push({ label: 'Off the grid', color: Colors.tierGem, bg: '#FFB80022' });
  return result;
}

/** @deprecated Use formatPrice() instead */
export function getSignalContext(place: PlaceOut): string {
  const tier = getTier(place.rank_score);
  switch (tier.key) {
    case 'crave_pick':
      if (place.has_menu && place.grubhub_url) return 'Full menu · Online ordering · Top ranked';
      if (place.has_menu) return 'Full menu · Culturally validated';
      return 'Locally loved · Off the beaten path';
    case 'gem':
      if (!place.has_menu && !place.grubhub_url) return 'Off the grid · Locals know this';
      if (!place.grubhub_url) return 'Community favorite · No delivery';
      return 'Local pick · Worth the visit';
    case 'solid':
      if (place.has_menu) return 'Menu available · Reliable choice';
      if (place.website) return 'Established · Worth exploring';
      return 'Solid choice';
    case 'new':
    default:
      return 'New to CRAVE · Still gaining signal';
  }
}
