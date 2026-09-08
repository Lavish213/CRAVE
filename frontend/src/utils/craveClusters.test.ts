import { deriveCraveClusters } from './craveClusters';
import { SavedPlace } from '../api/saves';

function makeSave(overrides: Partial<SavedPlace> = {}): SavedPlace {
  return {
    id: `p-${Math.random()}`,
    name: 'Place',
    city_id: 'city-sf',
    rank_score: 8,
    tier: 'gem',
    rank_percentile: 0.7,
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
    has_video: false,
    price_tier: null,
    visited: false,
    visited_at: null,
    notes: null,
    reason_role: null,
    reason_source: null,
    visit_confirmation_count: 0,
    ...overrides,
  };
}

describe('deriveCraveClusters', () => {
  it('returns no clusters when the saved pool is small, even if uniform', () => {
    const saves = [
      makeSave({ id: 'a', category: 'Ramen' }),
      makeSave({ id: 'b', category: 'Ramen' }),
      makeSave({ id: 'c', category: 'Ramen' }),
    ];
    expect(deriveCraveClusters(saves, null)).toEqual([]);
  });

  it('clusters by cuisine once the pool is large and varied enough', () => {
    const saves = [
      makeSave({ id: 'r1', category: 'Ramen' }),
      makeSave({ id: 'r2', category: 'Ramen' }),
      makeSave({ id: 'r3', category: 'Ramen' }),
      makeSave({ id: 't1', category: 'Tacos' }),
      makeSave({ id: 't2', category: 'Tacos' }),
      makeSave({ id: 'p1', category: 'Pizza' }),
    ];
    const clusters = deriveCraveClusters(saves, null);
    expect(clusters).toHaveLength(1);
    expect(clusters[0]).toMatchObject({ id: 'cuisine:Ramen', label: 'Ramen' });
    expect(clusters[0].items.map((i) => i.id)).toEqual(['r1', 'r2', 'r3']);
  });

  it('does not cluster a category that covers the entire pool', () => {
    const saves = Array.from({ length: 6 }, (_, i) => makeSave({ id: `s${i}`, category: 'Ramen' }));
    expect(deriveCraveClusters(saves, null)).toEqual([]);
  });

  it('caps cuisine clusters and keeps the largest ones', () => {
    const saves = [
      ...Array.from({ length: 3 }, (_, i) => makeSave({ id: `a${i}`, category: 'Ramen' })),
      ...Array.from({ length: 3 }, (_, i) => makeSave({ id: `b${i}`, category: 'Tacos' })),
      ...Array.from({ length: 3 }, (_, i) => makeSave({ id: `c${i}`, category: 'Pizza' })),
      ...Array.from({ length: 3 }, (_, i) => makeSave({ id: `d${i}`, category: 'Sushi' })),
      makeSave({ id: 'x', category: 'Diner' }),
    ];
    const clusters = deriveCraveClusters(saves, null);
    expect(clusters).toHaveLength(3);
  });

  it('does not produce geography clusters without a known user location', () => {
    const saves = Array.from({ length: 6 }, (_, i) =>
      makeSave({ id: `s${i}`, lat: 37.77 + i * 0.001, lng: -122.4 }));
    expect(deriveCraveClusters(saves, null)).toEqual([]);
  });

  it('clusters "Near Home" for places within a few miles of the user', () => {
    const near = Array.from({ length: 3 }, (_, i) =>
      makeSave({ id: `near${i}`, lat: 37.7749 + i * 0.001, lng: -122.4194 }));
    const far = Array.from({ length: 3 }, (_, i) =>
      makeSave({ id: `far${i}`, lat: 37.7749 + i * 0.001, lng: -121.0 }));
    const clusters = deriveCraveClusters([...near, ...far], { lat: 37.7749, lng: -122.4194 });
    const nearHome = clusters.find((c) => c.id === 'geo:near-home');
    expect(nearHome?.items.map((i) => i.id).sort()).toEqual(['near0', 'near1', 'near2']);
  });

  it('clusters "Worth the Drive" for places well outside the user\'s area', () => {
    const near = Array.from({ length: 3 }, (_, i) =>
      makeSave({ id: `near${i}`, lat: 37.7749 + i * 0.001, lng: -122.4194 }));
    const far = Array.from({ length: 3 }, (_, i) =>
      makeSave({ id: `far${i}`, lat: 37.7749 + i * 0.001, lng: -121.0 }));
    const clusters = deriveCraveClusters([...near, ...far], { lat: 37.7749, lng: -122.4194 });
    const worthTheDrive = clusters.find((c) => c.id === 'geo:worth-the-drive');
    expect(worthTheDrive?.items.map((i) => i.id).sort()).toEqual(['far0', 'far1', 'far2']);
  });

  it('skips places with no coordinates when building geography clusters', () => {
    const saves = [
      ...Array.from({ length: 3 }, (_, i) => makeSave({ id: `near${i}`, lat: 37.7749, lng: -122.4194 })),
      ...Array.from({ length: 3 }, (_, i) => makeSave({ id: `nogeo${i}`, lat: null, lng: null })),
    ];
    const clusters = deriveCraveClusters(saves, { lat: 37.7749, lng: -122.4194 });
    const nearHome = clusters.find((c) => c.id === 'geo:near-home');
    expect(nearHome?.items).toHaveLength(3);
  });
});
