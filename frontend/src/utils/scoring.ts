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

// Absolute rank_score bands. Kept only as a fallback for places with no
// ranking snapshot yet (rankPercentile === null/undefined below) -- e.g.
// a brand-new city, or a place added since the last hourly
// city_ranking_worker run. NOT used when a percentile is available.
//
// Why not the primary mechanism: place_score_v4's structural bucket caps
// at 0.28, and any normally-populated place (name, location, a few
// photos, a website or menu) hits close to that cap by default, while
// the cultural-signal buckets (blog/creator mentions) stay near zero for
// most places in a cold-start catalog. That clusters almost the entire
// catalog in a narrow band straddling the 0.22/0.32 boundary -- nearly
// everything reads as "Hidden Gem" or "Worth Knowing" regardless of
// actual quality, since the thresholds were never validated against the
// real score distribution. Confirmed live: a Search screen where 30/30
// results were tagged one of those two tiers, none "CRAVE Pick", none
// "Explore".
function tierFromAbsoluteScore(score: number): Tier {
  if (score >= 0.42) return TIERS.crave_pick;
  if (score >= 0.32) return TIERS.gem;
  if (score >= 0.22) return TIERS.solid;
  return TIERS.new;
}

// Percentile bands -- a place's standing relative to every other place in
// its own city, not an absolute score. This is what actually
// differentiates "genuinely exceptional" from "merely complete," and it
// self-corrects as the catalog and its signal (saves, mentions, awards)
// grow, unlike absolute thresholds which would need re-tuning every time
// the underlying score distribution shifts.
function tierFromPercentile(percentile: number): Tier {
  if (percentile >= 0.95) return TIERS.crave_pick;
  if (percentile >= 0.80) return TIERS.gem;
  if (percentile >= 0.40) return TIERS.solid;
  return TIERS.new;
}

export function getTier(score: number, rankPercentile?: number | null): Tier {
  if (typeof rankPercentile === 'number') return tierFromPercentile(rankPercentile);
  return tierFromAbsoluteScore(score);
}

// Two confirmed call sites (place/[id].tsx, (tabs)/index.tsx) previously
// called getTier(place.rank_score) without threading rank_percentile
// through -- the two-argument form makes that mistake easy to make and
// impossible for the compiler to catch, since both args are individually
// optional-looking numbers. Anything that already has a full place object
// (which is every real call site) should use this instead: there is no
// way to call it and forget the percentile, because there's only one
// thing to pass in.
export function getTierForPlace(place: {
  rank_score: number;
  rank_percentile?: number | null;
}): Tier {
  return getTier(place.rank_score, place.rank_percentile);
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

// ─── Distance ────────────────────────────────────────────────────────────────

/**
 * Great-circle distance in miles between two lat/lng points. Feed/Search
 * get `distance_miles` pre-computed server-side (lat/lng sent as query
 * params); Place Detail's GET /place/{id} takes no location params, so
 * distance there has to be computed client-side from useLocation() +
 * place.lat/lng instead of silently omitted.
 */
export function computeDistanceMiles(
  lat1: number, lng1: number, lat2: number, lng2: number,
): number {
  const R_MILES = 3958.8;
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return R_MILES * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/** Was duplicated identically in PlaceCard.tsx and PlaceCardCompact.tsx. */
export function formatDistance(distanceMiles: number | null | undefined): string | null {
  if (distanceMiles == null) return null;
  if (distanceMiles < 0.1) return 'Here';
  if (distanceMiles < 10) return `${distanceMiles.toFixed(1)} mi`;
  return `${Math.round(distanceMiles)} mi`;
}

// ─── Badges (emoji chips) ────────────────────────────────────────────────────

export interface Badge {
  emoji: string;
  label: string;
}

/**
 * Returns 0-1 contextual emoji chips for a place card -- menu/order
 * access, or its absence. Used to badge a quality tier here too, via
 * getTierForPlace() -- but every real call site (PlaceCard,
 * PlaceCardCompact) already renders <TierBadge> for that, so a second
 * "⭐ CRAVE Pick" chip in the body was pure duplication of the badge
 * already sitting on the same card's image. Removed rather than kept
 * "for safety" -- found during the Feed forensic inventory, same
 * duplication class as Place Detail's badge-chip row.
 */
export function getBadges(place: PlaceOut): Badge[] {
  const badges: Badge[] = [];

  if (place.has_menu && place.grubhub_url) {
    badges.push({ emoji: '🛵', label: 'Delivery' });
  } else if (place.has_menu) {
    badges.push({ emoji: '📋', label: 'Menu' });
  } else if (!place.grubhub_url && !place.website) {
    badges.push({ emoji: '🗺️', label: 'Off the grid' });
  }

  return badges;
}

/**
 * Card-level "why it matters" caption -- only for the two tiers where a
 * percentile claim actually reads as a reason to care (top 20%
 * catalog-wide). "Top 55%" would read as an anti-signal, not a
 * recommendation, so tiers below crave_pick/gem stay silent rather than
 * show a technically-true but discouraging number.
 */
export function percentileCaption(tier: Tier, rankPercentile: number | null | undefined): string | null {
  if (tier.key !== 'crave_pick' && tier.key !== 'gem') return null;
  if (rankPercentile == null) return null;
  return `Top ${Math.max(1, Math.round((1 - rankPercentile) * 100))}%`;
}

