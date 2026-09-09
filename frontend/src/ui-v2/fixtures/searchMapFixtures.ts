import type { PlaceOut } from '../../api/places';

function place(overrides: Partial<PlaceOut>): PlaceOut {
  return {
    id: 'fixture-place',
    name: 'Night Market Kitchen',
    city_id: 'fixture-city',
    rank_score: 91,
    tier: 'crave_pick',
    rank_percentile: 0.96,
    distance_miles: 1.2,
    category: 'Thai',
    categories: ['Thai'],
    address: '123 Fixture Ave',
    lat: 37.8044,
    lng: -122.2712,
    image: 'https://images.unsplash.com/photo-1559314809-0d155014e29e',
    primary_image_url: null,
    images: [],
    website: null,
    grubhub_url: null,
    has_menu: true,
    has_video: false,
    price_tier: 2,
    price: '$$',
    ...overrides,
  };
}

export const searchMapFixtures = {
  goodPhoto: place({ id: 'good-photo' }),
  noPhoto: place({ id: 'no-photo', name: 'No Photo Noodle House', image: null, primary_image_url: null }),
  longName: place({
    id: 'long-name',
    name: 'Taqueria El Buen Sabor Authentic Regional Mexican Kitchen & Family Restaurant',
    category: 'Regional Mexican',
    categories: ['Regional Mexican'],
  }),
  missingPrice: place({ id: 'missing-price', name: 'Corner Table', price_tier: null, price: undefined }),
  supporting: place({ id: 'supporting', name: 'Mela House', category: 'Indian', categories: ['Indian'], distance_miles: 2.8 }),
  closed: place({ id: 'closed', name: 'After Hours Ramen', category: 'Ramen', categories: ['Ramen'] }),
} as const;

export const hostilePhotoUrls = {
  veryDark: 'https://images.unsplash.com/photo-1515003197210-e0cd71810b5f',
  portrait: 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c',
  overexposed: 'https://images.unsplash.com/photo-1498837167922-ddd27525d352',
  failed: 'https://invalid.example.invalid/crave-ui-v2-fixture.jpg',
} as const;
