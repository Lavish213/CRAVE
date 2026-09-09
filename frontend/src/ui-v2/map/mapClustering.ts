import type { Region } from 'react-native-maps';
import type { NormalizedMapFeature } from '../../api/map';

const STREET_CLUSTER_RADIUS = 44;
const NEIGHBORHOOD_CLUSTER_RADIUS = 56;
const CITY_CLUSTER_RADIUS_MIN = 64;
const CITY_CLUSTER_RADIUS_MAX = 84;

export interface MapClusterPoint {
  key: string;
  latitude: number;
  longitude: number;
  count: number;
  feature?: NormalizedMapFeature;
}

interface CollisionCluster {
  key: string;
  members: NormalizedMapFeature[];
  x: number;
  y: number;
  sumLat: number;
  sumLng: number;
}

export function buildMapClusters(
  features: readonly NormalizedMapFeature[],
  region: Region,
  viewportWidth: number,
  viewportHeight: number,
): MapClusterPoint[] {
  const densityBoost = Math.min(20, Math.max(0, features.length - 60) / 10);
  const radiusPx = region.longitudeDelta <= 0.005
    ? STREET_CLUSTER_RADIUS
    : region.longitudeDelta <= 0.02
      ? NEIGHBORHOOD_CLUSTER_RADIUS
      : Math.min(CITY_CLUSTER_RADIUS_MAX, CITY_CLUSTER_RADIUS_MIN + densityBoost);
  const safeWidth = Math.max(1, viewportWidth);
  const safeHeight = Math.max(1, viewportHeight);
  const west = region.longitude - region.longitudeDelta / 2;
  const north = region.latitude + region.latitudeDelta / 2;

  const collisionClusters: CollisionCluster[] = [];
  for (const feature of features) {
    const x = ((feature.coordinate.lng - west) / region.longitudeDelta) * safeWidth;
    const y = ((north - feature.coordinate.lat) / region.latitudeDelta) * safeHeight;
    let nearest: CollisionCluster | undefined;
    let nearestDistance = Number.POSITIVE_INFINITY;

    for (const candidate of collisionClusters) {
      const distance = Math.hypot(candidate.x - x, candidate.y - y);
      if (distance < radiusPx && distance < nearestDistance) {
        nearest = candidate;
        nearestDistance = distance;
      }
    }

    if (!nearest) {
      collisionClusters.push({
        key: feature.id,
        members: [feature],
        x,
        y,
        sumLat: feature.coordinate.lat,
        sumLng: feature.coordinate.lng,
      });
      continue;
    }

    nearest.members.push(feature);
    nearest.sumLat += feature.coordinate.lat;
    nearest.sumLng += feature.coordinate.lng;
    nearest.x = nearest.members.reduce(
      (sum, member) => sum + ((member.coordinate.lng - west) / region.longitudeDelta) * safeWidth,
      0,
    ) / nearest.members.length;
    nearest.y = nearest.members.reduce(
      (sum, member) => sum + ((north - member.coordinate.lat) / region.latitudeDelta) * safeHeight,
      0,
    ) / nearest.members.length;
  }

  return collisionClusters.map((cluster) => {
    if (cluster.members.length === 1) {
      const feature = cluster.members[0];
      return {
        key: `point:${feature.id}`,
        latitude: feature.coordinate.lat,
        longitude: feature.coordinate.lng,
        count: 1,
        feature,
      };
    }

    return {
      key: `cluster:${cluster.key}`,
      latitude: cluster.sumLat / cluster.members.length,
      longitude: cluster.sumLng / cluster.members.length,
      count: cluster.members.length,
    };
  });
}

export function isCoordinateInsideRegion(
  latitude: number,
  longitude: number,
  region: Region,
): boolean {
  const halfLat = region.latitudeDelta / 2;
  const halfLng = region.longitudeDelta / 2;
  return (
    latitude >= region.latitude - halfLat &&
    latitude <= region.latitude + halfLat &&
    longitude >= region.longitude - halfLng &&
    longitude <= region.longitude + halfLng
  );
}
