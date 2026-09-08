// src/utils/craveClusters.ts
//
// Craves Screen Contract §6's "automatic clusters" -- cuisine/geography-
// derived groupings ("Ramen," "Near Home," "Worth the Drive") over the
// native saved pool. Purely client-side over data already on each
// SavedPlace (category, lat/lng); no new backend endpoint, matching
// contract §8 ("Craves' net-new need is entirely on the intelligence
// side... not the component side").
//
// Deliberately cuisine + geography only. The contract's own examples never
// include an occasion cluster ("date night," "breakfast"), and there is no
// occasion signal anywhere in the data model to derive one honestly from --
// fabricating one would be inventing a signal, not deriving it.
import { SavedPlace } from '../api/saves';
import { computeDistanceMiles } from './scoring';
import { UserLocation } from '../hooks/useLocation';

export interface CraveCluster {
  id: string;
  label: string;
  subtext: string;
  items: SavedPlace[];
}

// Contract §6: "present only when the saved pool is large/varied enough to
// cluster meaningfully; a small pool shows the reasoned subset and a flat
// full list with no clustering UI at all."
const MIN_POOL_FOR_CLUSTERING = 6;
const MIN_CLUSTER_SIZE = 3;
const MAX_CUISINE_CLUSTERS = 3;
const NEAR_HOME_MILES = 3;
const WORTH_THE_DRIVE_MILES = 10;

export function deriveCraveClusters(
  saves: SavedPlace[],
  userLocation: UserLocation | null,
): CraveCluster[] {
  if (saves.length < MIN_POOL_FOR_CLUSTERING) return [];

  const clusters: CraveCluster[] = [];

  const byCategory = new Map<string, SavedPlace[]>();
  for (const place of saves) {
    if (!place.category) continue;
    const bucket = byCategory.get(place.category);
    if (bucket) bucket.push(place);
    else byCategory.set(place.category, [place]);
  }
  Array.from(byCategory.entries())
    // A category covering every single save isn't variety, it's the whole
    // pool -- no point clustering it out separately.
    .filter(([, items]) => items.length >= MIN_CLUSTER_SIZE && items.length < saves.length)
    .sort((a, b) => b[1].length - a[1].length)
    .slice(0, MAX_CUISINE_CLUSTERS)
    .forEach(([category, items]) => {
      clusters.push({
        id: `cuisine:${category}`,
        label: category,
        subtext: `${items.length} of your saves`,
        items,
      });
    });

  if (userLocation) {
    const withDistance = saves
      .filter((p): p is SavedPlace & { lat: number; lng: number } => p.lat != null && p.lng != null)
      .map((p) => ({
        place: p,
        miles: computeDistanceMiles(userLocation.lat, userLocation.lng, p.lat, p.lng),
      }));

    const nearHome = withDistance.filter((p) => p.miles <= NEAR_HOME_MILES).map((p) => p.place);
    if (nearHome.length >= MIN_CLUSTER_SIZE) {
      clusters.push({
        id: 'geo:near-home',
        label: 'Near Home',
        subtext: `Within ${NEAR_HOME_MILES} miles`,
        items: nearHome,
      });
    }

    const worthTheDrive = withDistance.filter((p) => p.miles >= WORTH_THE_DRIVE_MILES).map((p) => p.place);
    if (worthTheDrive.length >= MIN_CLUSTER_SIZE) {
      clusters.push({
        id: 'geo:worth-the-drive',
        label: 'Worth the Drive',
        subtext: `${WORTH_THE_DRIVE_MILES}+ miles away`,
        items: worthTheDrive,
      });
    }
  }

  return clusters;
}
