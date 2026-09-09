import React from 'react';
import MapScreenCore from '../../src/screens/MapScreenCore';
import { useDiscoveryContextStore } from '../../src/stores/discoveryContextStore';
import { buildMapClusters } from '../../src/ui-v2/map/mapClustering';

export { buildMapClusters as buildClusters };

/**
 * Route boundary for the contextual Map.
 *
 * A Search handoff is a new recommendation context even when query/scope are
 * textually identical to the previous handoff. Keying the core by the search
 * session deliberately remounts its local view state so stale Map filters and
 * exposure refs cannot leak across Search sessions. The mature Map behavior
 * remains isolated in MapScreenCore.
 */
export default function MapScreen() {
  const searchSessionId = useDiscoveryContextStore(
    (state) => state.searchMapHandoff?.searchSessionId ?? null,
  );

  return (
    <MapScreenCore
      key={searchSessionId ? `search:${searchSessionId}` : 'contextual-map'}
    />
  );
}
