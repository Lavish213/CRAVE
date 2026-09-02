// Regression coverage for the missing-media fix: a no-image card must
// consume materially less vertical space than an image-backed card, and
// clearly communicate that no photo is available, instead of reserving
// the same giant hero area a real photo would (CRAVE_MASTER_EXECUTION_ROADMAP.md
// Phase 1 / docs/CLAUDE_EXECUTION_BRIEF_SCREEN_AND_COVERAGE_2026-09-02.md
// Track 1, item 2).
import React from 'react';
import { render } from '@testing-library/react-native';
import { PlaceCard } from './PlaceCard';
import type { PlaceOut } from '../api/places';

jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  notificationAsync: jest.fn(),
  ImpactFeedbackStyle: { Light: 'light', Medium: 'medium' },
  NotificationFeedbackType: { Success: 'success', Warning: 'warning', Error: 'error' },
}));

function makePlace(overrides: Partial<PlaceOut> = {}): PlaceOut {
  return {
    id: 'place-1',
    name: 'Nari',
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
    has_video: false,
    price_tier: null,
    ...overrides,
  } as PlaceOut;
}

function flatHeight(node: any): number {
  const style = Array.isArray(node.props.style)
    ? Object.assign({}, ...node.props.style)
    : node.props.style;
  return style.height;
}

describe('PlaceCard missing-media state', () => {
  it('renders a materially shorter fallback than a real photo, with an honest no-photo label', () => {
    const { getByLabelText } = render(
      <PlaceCard place={makePlace({ image: null })} onPress={() => {}} onSave={() => {}} saved={false} />
    );

    const fallback = getByLabelText('No photo yet for Nari');
    expect(flatHeight(fallback)).toBeLessThan(150); // materially less than IMAGE_HEIGHT (220)
  });

  it('does not render the no-photo state when a real image exists', () => {
    const { queryByLabelText } = render(
      <PlaceCard
        place={makePlace({ image: 'https://example.com/photo.jpg' })}
        onPress={() => {}}
        onSave={() => {}}
        saved={false}
      />
    );

    expect(queryByLabelText('No photo yet for Nari')).toBeNull();
  });
});
