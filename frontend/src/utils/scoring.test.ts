import { getTier, getTierForPlace, inferPrice, formatPrice, getBadges, percentileCaption, formatDistance, TIERS } from './scoring';
import type { PlaceOut } from '../api/places';

function makePlace(overrides: Partial<PlaceOut> = {}): PlaceOut {
  return {
    id: 'place-1',
    name: 'Test Place',
    city_id: 'city-1',
    rank_score: 0,
    tier: 'new',
    rank_percentile: null,
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

  // Percentile-based tiering: this place's standing within its own city
  // (0 = worst, 1 = best), used instead of the absolute score whenever
  // it's available. Fixes the bug where place_score_v4's structural cap
  // (0.28) clustered almost every normally-populated place into the same
  // narrow absolute-score band, making "Hidden Gem"/"Worth Knowing" show
  // up on nearly every result regardless of actual differentiation.
  describe('with rank_percentile', () => {
    it('ignores rank_score entirely and uses the percentile bands instead', () => {
      // A low absolute score that would be "new" on its own, but this
      // place is still the best in its (small/sparse) city.
      expect(getTier(0.05, 1.0).key).toBe('crave_pick');
      // A high absolute score that would be "crave_pick" on its own, but
      // this place is mid-pack relative to its city.
      expect(getTier(0.9, 0.5).key).toBe('solid');
    });

    it('returns crave_pick at and above the 0.95 percentile', () => {
      expect(getTier(0, 0.95).key).toBe('crave_pick');
      expect(getTier(0, 1.0).key).toBe('crave_pick');
    });

    it('returns gem between 0.80 and 0.95 percentile', () => {
      expect(getTier(0, 0.8).key).toBe('gem');
      expect(getTier(0, 0.949).key).toBe('gem');
    });

    it('returns solid between 0.40 and 0.80 percentile', () => {
      expect(getTier(0, 0.4).key).toBe('solid');
      expect(getTier(0, 0.799).key).toBe('solid');
    });

    it('returns new below 0.40 percentile', () => {
      expect(getTier(0, 0).key).toBe('new');
      expect(getTier(0, 0.399).key).toBe('new');
    });

    it('falls back to absolute-score tiering when percentile is null', () => {
      expect(getTier(0.5, null).key).toBe(getTier(0.5).key);
    });

    it('falls back to absolute-score tiering when percentile is undefined', () => {
      expect(getTier(0.5, undefined).key).toBe(getTier(0.5).key);
    });
  });
});

describe('getTierForPlace', () => {
  // The whole point of this wrapper: a caller that already has a place
  // object can't forget to pass rank_percentile, because there's no
  // second argument to forget. Pinning that contract here so it can't
  // silently regress back to the two-argument footgun.
  it('uses rank_percentile when present, matching getTier(score, percentile)', () => {
    const place = makePlace({ rank_score: 0.05, rank_percentile: 1.0 });
    expect(getTierForPlace(place).key).toBe(getTier(0.05, 1.0).key);
    expect(getTierForPlace(place).key).toBe('crave_pick');
  });

  it('falls back to absolute-score tiering when rank_percentile is null, matching getTier(score)', () => {
    const place = makePlace({ rank_score: 0.5, rank_percentile: null });
    expect(getTierForPlace(place).key).toBe(getTier(0.5).key);
  });

  it('falls back to absolute-score tiering when rank_percentile is absent from the object entirely', () => {
    expect(getTierForPlace({ rank_score: 0.5 }).key).toBe(getTier(0.5).key);
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
  it('does not badge tier -- TierBadge already renders it on every real call site', () => {
    const badges = getBadges(makePlace({ rank_score: 0.5 }));
    expect(badges.some((b) => b.label === 'CRAVE Pick' || b.label === 'Hidden Gem')).toBe(false);
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

  it('never returns more than one badge -- the three cases are mutually exclusive', () => {
    const badges = getBadges(
      makePlace({ rank_score: 0.5, has_menu: true, grubhub_url: 'https://grubhub.com/x' }),
    );
    expect(badges.length).toBeLessThanOrEqual(1);
  });
});

describe('percentileCaption', () => {
  it('captions a crave_pick tier with its real percentile', () => {
    expect(percentileCaption(TIERS.crave_pick, 0.97)).toBe('Top 3%');
  });

  it('captions a gem tier with its real percentile', () => {
    expect(percentileCaption(TIERS.gem, 0.85)).toBe('Top 15%');
  });

  it('stays silent for solid/new tiers -- "Top 55%" reads as an anti-signal, not a reason to care', () => {
    expect(percentileCaption(TIERS.solid, 0.55)).toBeNull();
    expect(percentileCaption(TIERS.new, 0.1)).toBeNull();
  });

  it('stays silent when no percentile snapshot exists yet, even for a top tier', () => {
    expect(percentileCaption(TIERS.crave_pick, null)).toBeNull();
  });
});

describe('formatDistance', () => {
  // Was duplicated identically in PlaceCard.tsx and PlaceCardCompact.tsx --
  // extracted here so both consume the same tested implementation.
  it('returns null when distance is not available', () => {
    expect(formatDistance(null)).toBeNull();
    expect(formatDistance(undefined)).toBeNull();
  });

  it('shows "Here" for sub-tenth-mile distances', () => {
    expect(formatDistance(0.05)).toBe('Here');
  });

  it('shows one decimal place under 10 miles', () => {
    expect(formatDistance(2.34)).toBe('2.3 mi');
  });

  it('rounds to a whole number at 10 miles and above', () => {
    expect(formatDistance(12.7)).toBe('13 mi');
  });
});
