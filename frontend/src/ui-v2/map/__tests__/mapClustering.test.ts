import type { Region } from 'react-native-maps';
import type { NormalizedMapFeature } from '../../../api/map';
import { buildMapClusters, isCoordinateInsideRegion } from '../mapClustering';

const region: Region = {
  latitude: 37.8,
  longitude: -122.27,
  latitudeDelta: 0.08,
  longitudeDelta: 0.08,
};

function feature(id: string, lat: number, lng: number): NormalizedMapFeature {
  return {
    id,
    name: id,
    coordinate: { lat, lng },
    tier: 'default',
    rank_score: 0,
    price_tier: null,
    image: null,
    category: null,
    has_menu: false,
    has_video: false,
  };
}

describe('Map V2 clustering', () => {
  it('keeps spatially separated places as individual points', () => {
    const clusters = buildMapClusters(
      [feature('a', 37.78, -122.29), feature('b', 37.82, -122.25)],
      region,
      390,
      844,
    );
    expect(clusters).toHaveLength(2);
    expect(clusters.every((cluster) => cluster.count === 1)).toBe(true);
  });

  it('clusters colliding places', () => {
    const clusters = buildMapClusters(
      [feature('a', 37.8, -122.27), feature('b', 37.8001, -122.2701)],
      region,
      390,
      844,
    );
    expect(clusters).toHaveLength(1);
    expect(clusters[0].count).toBe(2);
    expect(clusters[0].feature).toBeUndefined();
  });

  it('detects whether a coordinate is inside the visible region', () => {
    expect(isCoordinateInsideRegion(37.8, -122.27, region)).toBe(true);
    expect(isCoordinateInsideRegion(38.0, -122.27, region)).toBe(false);
  });
});
