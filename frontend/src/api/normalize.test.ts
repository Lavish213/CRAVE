import { normalizePlaceOut, normalizePlaces, normalizeMenuItems, normalizeMapFeatures } from './normalize';

describe('normalizePlaceOut', () => {
  it('fills in safe defaults for a completely empty/malformed input', () => {
    const result = normalizePlaceOut({});
    expect(result.id).toBe('');
    expect(result.name).toBe('Unknown');
    expect(result.rank_score).toBe(0);
    expect(result.tier).toBe('new');
    expect(result.categories).toEqual([]);
    expect(result.images).toEqual([]);
    expect(result.has_menu).toBe(false);
  });

  it('handles null/undefined input without throwing', () => {
    expect(() => normalizePlaceOut(null)).not.toThrow();
    expect(() => normalizePlaceOut(undefined)).not.toThrow();
  });

  it('derives tier from rank_score when the backend does not send one', () => {
    expect(normalizePlaceOut({ rank_score: 0.5 }).tier).toBe('crave_pick');
    expect(normalizePlaceOut({ rank_score: 0.35 }).tier).toBe('gem');
    expect(normalizePlaceOut({ rank_score: 0.25 }).tier).toBe('solid');
    expect(normalizePlaceOut({ rank_score: 0.1 }).tier).toBe('new');
  });

  it('trusts a valid backend-provided tier over the locally-derived one', () => {
    // rank_score alone would derive "new", but the backend says "gem".
    expect(normalizePlaceOut({ rank_score: 0.1, tier: 'gem' }).tier).toBe('gem');
  });

  it('ignores an invalid backend tier and falls back to local derivation', () => {
    expect(normalizePlaceOut({ rank_score: 0.5, tier: 'not_a_real_tier' }).tier).toBe('crave_pick');
  });

  it('filters generic categories out of the categories list', () => {
    const result = normalizePlaceOut({ categories: ['Restaurant', 'pizza', 'Other', ''] });
    expect(result.categories).toEqual(['pizza']);
  });

  it('prefers a specific top-level category over a generic one', () => {
    const result = normalizePlaceOut({ category: 'restaurant', categories: ['italian'] });
    expect(result.category).toBe('italian');
  });

  it('keeps a specific top-level category as-is', () => {
    const result = normalizePlaceOut({ category: 'mexican' });
    expect(result.category).toBe('mexican');
  });

  it('falls back to a non-void category when nothing specific is available', () => {
    const result = normalizePlaceOut({ category: 'Restaurant', categories: [] });
    expect(result.category).toBe('Restaurant');
  });

  it('returns null category when everything is void/generic', () => {
    const result = normalizePlaceOut({ category: 'other', categories: ['', 'others'] });
    expect(result.category).toBeNull();
  });

  it('resolves a relative /api/ image URL against the API base', () => {
    const result = normalizePlaceOut({ primary_image_url: '/api/v1/image/abc' });
    expect(result.image).toMatch(/\/api\/v1\/image\/abc$/);
  });

  it('leaves an absolute image URL untouched', () => {
    const result = normalizePlaceOut({ primary_image_url: 'https://cdn.example.com/x.jpg' });
    expect(result.image).toBe('https://cdn.example.com/x.jpg');
  });

  it('falls back through primary_image_url -> primary_image -> images[0]', () => {
    expect(normalizePlaceOut({ primary_image: 'https://cdn.example.com/a.jpg' }).image).toBe(
      'https://cdn.example.com/a.jpg',
    );
    expect(normalizePlaceOut({ images: ['https://cdn.example.com/b.jpg'] }).image).toBe(
      'https://cdn.example.com/b.jpg',
    );
  });

  it('populates a formatted price string via formatPrice', () => {
    const result = normalizePlaceOut({ price_tier: 2 });
    expect(result.price).toBe('$$');
  });
});

describe('normalizePlaces', () => {
  it('maps an array of raw places', () => {
    const result = normalizePlaces([{ id: '1' }, { id: '2' }]);
    expect(result.map((p) => p.id)).toEqual(['1', '2']);
  });

  it('returns an empty array for non-array input', () => {
    expect(normalizePlaces(null)).toEqual([]);
    expect(normalizePlaces({ not: 'an array' })).toEqual([]);
  });
});

describe('normalizeMenuItems', () => {
  it('normalizes a bare array of items', () => {
    const result = normalizeMenuItems([{ id: '1', name: 'Burger', price: 9.5 }]);
    expect(result).toEqual([
      { id: '1', name: 'Burger', description: null, price: 9.5, category: null },
    ]);
  });

  it('unwraps an { items: [...] } envelope', () => {
    const result = normalizeMenuItems({ items: [{ name: 'Fries' }] });
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe('Fries');
  });

  it('generates a fallback id when one is missing', () => {
    const result = normalizeMenuItems([{ name: 'Mystery Item' }]);
    expect(result[0].id).toBeTruthy();
  });

  it('returns an empty array for unrecognized shapes', () => {
    expect(normalizeMenuItems(null)).toEqual([]);
    expect(normalizeMenuItems({})).toEqual([]);
  });
});

describe('normalizeMapFeatures', () => {
  const validFeature = {
    geometry: { coordinates: [-122.27, 37.8] },
    properties: { id: 'p1', name: 'Test Spot', rank_score: 0.5, tier: 'elite' },
  };

  it('normalizes a valid GeoJSON feature, converting [lng, lat] to {lat, lng}', () => {
    const result = normalizeMapFeatures([validFeature]);
    expect(result).toHaveLength(1);
    expect(result[0].coordinate).toEqual({ lat: 37.8, lng: -122.27 });
    expect(result[0].id).toBe('p1');
  });

  it('unwraps a FeatureCollection-shaped { features: [...] } envelope', () => {
    const result = normalizeMapFeatures({ features: [validFeature] });
    expect(result).toHaveLength(1);
  });

  it('drops features with missing coordinates', () => {
    const result = normalizeMapFeatures([{ geometry: {}, properties: {} }]);
    expect(result).toEqual([]);
  });

  it('drops features with out-of-range coordinates', () => {
    const badLat = { geometry: { coordinates: [0, 200] }, properties: {} };
    const badLng = { geometry: { coordinates: [-200, 0] }, properties: {} };
    expect(normalizeMapFeatures([badLat, badLng])).toEqual([]);
  });

  it('drops features with non-finite coordinates', () => {
    const result = normalizeMapFeatures([{ geometry: { coordinates: [Infinity, 1] }, properties: {} }]);
    expect(result).toEqual([]);
  });

  it('falls back to the "default" tier for an unrecognized tier value', () => {
    const result = normalizeMapFeatures([
      { geometry: { coordinates: [0, 0] }, properties: { tier: 'not_a_tier' } },
    ]);
    expect(result[0].tier).toBe('default');
  });

  it('returns an empty array for a non-array, non-FeatureCollection input', () => {
    expect(normalizeMapFeatures(null)).toEqual([]);
    expect(normalizeMapFeatures({})).toEqual([]);
  });
});
