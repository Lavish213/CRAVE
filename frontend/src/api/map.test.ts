import { client } from './client';
import { fetchMapGeoJSON, fetchSavedPlacesGeoJSON } from './map';

jest.mock('./client', () => ({ client: { get: jest.fn() } }));

const mockedGet = client.get as jest.Mock;

describe('map API contracts', () => {
  beforeEach(() => {
    mockedGet.mockReset();
    mockedGet.mockResolvedValue({ data: { type: 'FeatureCollection', features: [] } });
  });

  it('threads cancellation through city and saved-map requests', async () => {
    const controller = new AbortController();

    await fetchMapGeoJSON({ lat: 1, lng: 2 }, controller.signal);
    await fetchSavedPlacesGeoJSON(controller.signal);

    expect(mockedGet).toHaveBeenNthCalledWith(1, '/api/v1/map/geojson', {
      params: { lat: 1, lng: 2 },
      signal: controller.signal,
    });
    expect(mockedGet).toHaveBeenNthCalledWith(2, '/api/v1/saves/map', {
      signal: controller.signal,
    });
  });

  it.each([
    ['city map', () => fetchMapGeoJSON({ lat: 1, lng: 2 })],
    ['saved map', () => fetchSavedPlacesGeoJSON()],
  ])('rejects malformed %s payloads instead of reporting false empty states', async (_label, request) => {
    mockedGet.mockResolvedValueOnce({ data: { features: null } });

    await expect(request()).rejects.toThrow('features must be an array');
  });
});
