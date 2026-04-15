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
    sectionSubtext: 'The strongest signals in the city',
  },
  gem: {
    key: 'gem',
    label: 'Hidden Gem',
    color: Colors.tierGem,
    sectionLabel: 'Hidden Gems',
    sectionSubtext: 'Off the beaten path, locally loved',
  },
  solid: {
    key: 'solid',
    label: 'Worth Knowing',
    color: Colors.tierSolid,
    sectionLabel: 'Worth Knowing',
    sectionSubtext: 'Solid choices with real upside',
  },
  new: {
    key: 'new',
    label: 'Explore',
    color: Colors.tierNew,
    sectionLabel: 'Explore',
    sectionSubtext: 'New to CRAVE or still emerging',
  },
};

export function getTier(score: number): Tier {
  if (score >= 0.42) return TIERS.crave_pick;
  if (score >= 0.32) return TIERS.gem;
  if (score >= 0.22) return TIERS.solid;
  return TIERS.new;
}

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

export interface TrustBadge {
  label: string;
  color: string;
  bg: string;
}

export function getTrustBadges(place: PlaceOut): TrustBadge[] {
  const badges: TrustBadge[] = [];
  const tier = getTier(place.rank_score);
  if (tier.key === 'crave_pick')
    badges.push({ label: 'CRAVE Pick', color: Colors.tierCravePick, bg: '#FF4D0022' });
  if (tier.key === 'gem')
    badges.push({ label: 'Hidden Gem', color: Colors.tierGem, bg: '#FFB80022' });
  if (place.has_menu)
    badges.push({ label: 'Full menu', color: Colors.tierSolid, bg: '#4CAF5022' });
  if (place.grubhub_url)
    badges.push({ label: 'Order online', color: Colors.textSecondary, bg: '#88888822' });
  if (place.website && !place.grubhub_url)
    badges.push({ label: 'Dine in only', color: Colors.textSecondary, bg: '#88888822' });
  if (!place.has_menu && !place.grubhub_url && !place.website)
    badges.push({ label: 'Off the grid', color: Colors.tierGem, bg: '#FFB80022' });
  return badges;
}
