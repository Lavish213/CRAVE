import React from 'react';
import { Share } from 'react-native';
import { render, fireEvent } from '@testing-library/react-native';
import { PlaceCard } from './PlaceCard';
import { PlaceOut } from '../api/places';

const PLACE: PlaceOut = {
  id: 'place-1',
  name: 'Test Bistro',
  city_id: 'city-1',
  rank_score: 0.9,
  tier: 'gem',
  rank_percentile: 0.8,
  distance_miles: 1.2,
  category: 'Italian',
  categories: ['Italian'],
  address: '123 Main St, Testville',
  lat: 37.8,
  lng: -122.27,
  image: null,
  primary_image_url: null,
  images: [],
} as unknown as PlaceOut;

describe('PlaceCard long-press share', () => {
  it('shares the real https:// universal link, not just plain text', () => {
    const shareSpy = jest.spyOn(Share, 'share').mockResolvedValue({ action: 'sharedAction' } as never);

    const { getByLabelText } = render(
      <PlaceCard
        place={PLACE}
        onPress={() => {}}
        onSave={() => {}}
        saved={false}
      />,
    );

    fireEvent(getByLabelText('Test Bistro, Italian, Hidden Gem'), 'longPress');

    expect(shareSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        message: expect.stringContaining('https://crave.app/place/place-1'),
      }),
    );
  });
});
