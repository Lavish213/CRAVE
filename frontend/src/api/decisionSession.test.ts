import { client } from './client';
import { fetchDecisionSession } from './decisionSession';

jest.mock('./client', () => ({
  client: { get: jest.fn() },
}));

const mockedGet = client.get as jest.Mock;

describe('fetchDecisionSession', () => {
  beforeEach(() => {
    mockedGet.mockReset();
  });

  it('requests the frozen endpoint contract and normalizes every returned place', async () => {
    mockedGet.mockResolvedValue({
      data: {
        cards: [
          {
            place: {
              id: 'best-1',
              name: 'Best One',
              city_id: 'city-sf',
              rank_score: 0.9,
              tier: 'crave_pick',
              rank_percentile: 0.98,
              distance_miles: 1.2,
              category: 'Italian',
              categories: ['Italian'],
              address: null,
              lat: null,
              lng: null,
              image: null,
              primary_image_url: null,
              images: [],
              website: null,
              grubhub_url: null,
              has_menu: false,
              price_tier: 2,
            },
            role: 'best_fit',
            reason_codes: ['top_ranked_in_area'],
          },
        ],
        degraded: true,
      },
    });

    const result = await fetchDecisionSession({
      city_id: 'city-sf',
      radius_miles: 20,
    });

    expect(mockedGet).toHaveBeenCalledWith('/api/v1/decision-session', {
      params: { city_id: 'city-sf', radius_miles: 20 },
    });
    expect(result).toEqual({
      cards: [
        expect.objectContaining({
          role: 'best_fit',
          reason_codes: ['top_ranked_in_area'],
          place: expect.objectContaining({ id: 'best-1', price: '$$' }),
        }),
      ],
      degraded: true,
    });
  });

  it('treats a malformed cards payload as an empty degraded session', async () => {
    mockedGet.mockResolvedValue({ data: { cards: null, degraded: false } });

    await expect(fetchDecisionSession({})).resolves.toEqual({
      cards: [],
      degraded: true,
    });
  });
});
