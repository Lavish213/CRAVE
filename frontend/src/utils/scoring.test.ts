import { getTier, inferPrice, formatPrice, getBadges, TIERS } from './scoring';
import type { PlaceOut } from '../api/places';

function makePlace(overrides: Partial<PlaceOut> = {}): PlaceOut {
  return {
    id: 'place-1',
    name: 'Test Place',
    city_id: 'city-1',
    rank_score: 0,
    tier: 'new',
    distance_miles: null,
    category: null,
    categories: [],
    address: null,
    lat: null,
    lng: null,
    image: null,
    primary_image_url: null,
    images: [],
    website: null,
    grubhub_url: null,
    has_menu: false,
    price_tier: null,
    ...overrides,
  };
}

describe('getTier', () => {
  it('returns crave_pick at and above the 0.42 threshold', () => {
    expect(getTier(0.42).key).toBe('crave_pick');
    expect(getTier(0.9).key).toBe('crave_pick');
  });

  it('returns gem between 0.32 and 0.42', () => {
    expect(getTier(0.32).key).toBe('gem');
    expect(getTier(0.419).key).toBe('gem');
  });

  it('returns solid between 0.22 and 0.32', () => {
    expect(getTier(0.22).key).toBe('solid');
    expect(getTier(0.319).key).toBe('solid');
  });

  it('returns new below 0.22', () => {
    expect(getTier(0).key).toBe('new');
    expect(getTier(0.219).key).toBe('new');
  });

  it('every tier key maps back to a TIERS entry with matching key', () => {
    for (const score of [0, 0.25, 0.35, 0.5]) {
      const tier = getTier(score);
      expect(TIERS[tier.key].key).toBe(tier.key);
    }
  });
});

describe('inferPrice', () => {
  it('returns the explicit price_tier when set, even if name suggests otherwise', () => {
    expect(inferPrice(makePlace({ price_tier: 2, name: 'Fine Dining Tasting Menu' }))).toBe(2);
  });

  it('infers 4 from a price-4 keyword in the name', () => {
    expect(inferPrice(makePlace({ name: "Chez Omakase" }))).toBe(4);
  });

  it('infers 3 from a price-3 keyword in the category', () => {
    expect(inferPrice(makePlace({ name: 'Joe\'s', category: 'steakhouse' }))).toBe(3);
  });

  it('infers 1 from a price-1 keyword in categories', () => {
    expect(inferPrice(makePlace({ name: 'Joe\'s', categories: ['taco stand'] }))).toBe(1);
  });

  it('returns null when nothing matches and price_tier is unset', () => {
    expect(inferPrice(makePlace({ name: 'Generic Restaurant' }))).toBeNull();
  });

  it('prioritizes price-4 keywords over price-1 keywords when both present', () => {
    // "food truck" (price 1) and "michelin" (price 4) both present —
    // implementation checks PRICE_4_KEYWORDS first.
    expect(inferPrice(makePlace({ name: 'Michelin food truck' }))).toBe(4);
  });
});

describe('formatPrice', () => {
  it('formats a price tier as repeated dollar signs', () => {
    expect(formatPrice(makePlace({ price_tier: 3 }))).toBe('$$$');
  });

  it('returns null when price cannot be inferred', () => {
    expect(formatPrice(makePlace({ name: 'Generic Restaurant' }))).toBeNull();
  });
});

describe('getBadges', () => {
  it('badges a crave_pick tier place', () => {
    const badges = getBadges(makePlace({ rank_score: 0.5 }));
    expect(badges.some((b) => b.label === 'CRAVE Pick')).toBe(true);
  });

  it('badges a gem tier place', () => {
    const badges = getBadges(makePlace({ rank_score: 0.35 }));
    expect(badges.some((b) => b.label === 'Hidden Gem')).toBe(true);
  });

  it('shows Delivery when the place has a menu and a grubhub url', () => {
    const badges = getBadges(makePlace({ has_menu: true, grubhub_url: 'https://grubhub.com/x' }));
    expect(badges.some((b) => b.label === 'Delivery')).toBe(true);
  });

  it('shows Menu (not Delivery) when the place has a menu but no grubhub url', () => {
    const badges = getBadges(makePlace({ has_menu: true, grubhub_url: null }));
    expect(badges.some((b) => b.label === 'Menu')).toBe(true);
    expect(badges.some((b) => b.label === 'Delivery')).toBe(false);
  });

  it('shows Off the grid when there is no menu, grubhub url, or website', () => {
    const badges = getBadges(makePlace({ has_menu: false, grubhub_url: null, website: null }));
    expect(badges.some((b) => b.label === 'Off the grid')).toBe(true);
  });

  it('never returns more than 3 badges', () => {
    const badges = getBadges(
      makePlace({ rank_score: 0.5, has_menu: true, grubhub_url: 'https://grubhub.com/x' }),
    );
    expect(badges.length).toBeLessThanOrEqual(3);
  });
});
