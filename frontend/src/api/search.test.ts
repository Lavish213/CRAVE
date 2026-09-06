import { client } from './client';
import { searchPlaces } from './search';

jest.mock('./client', () => ({
  client: { get: jest.fn() },
}));

const mockedGet = client.get as jest.Mock;

describe('searchPlaces', () => {
  beforeEach(() => {
    mockedGet.mockReset();
    mockedGet.mockResolvedValue({ data: { total: 0, page: 1, page_size: 20, items: [] } });
  });

  it('forwards an AbortSignal to the underlying request, so a superseded query actually cancels the HTTP call instead of just being ignored once it resolves', async () => {
    const controller = new AbortController();

    await searchPlaces({ query: 'ramen' }, controller.signal);

    expect(mockedGet).toHaveBeenCalledWith('/api/v1/search', {
      params: { query: 'ramen' },
      signal: controller.signal,
    });
  });

  it('still works with no signal (the pre-existing call shape)', async () => {
    await searchPlaces({ query: 'ramen' });

    expect(mockedGet).toHaveBeenCalledWith('/api/v1/search', {
      params: { query: 'ramen' },
      signal: undefined,
    });
  });
});
