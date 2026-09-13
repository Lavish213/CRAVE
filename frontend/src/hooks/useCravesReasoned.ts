import { useQuery } from '@tanstack/react-query';
import { fetchCravesReasoned } from '../api/crave';
import { useAuthStore } from '../stores/authStore';
import { useLocation } from './useLocation';
import { foundationQueryKey, STALE_TIME } from '../contracts/foundationGate';

/**
 * Craves Screen Contract §5/§6's "reasoned subset" -- the same
 * build_decision_session() engine as Decision Session, scoped to this
 * user's saved pool. Auth-gated: Craves is inherently a signed-in,
 * personal surface (contract §12), so this never runs signed out.
 */
export function useCravesReasoned() {
  const user = useAuthStore((state) => state.user);
  const location = useLocation();

  return useQuery({
    queryKey: user
      ? foundationQueryKey({
          scope: 'user',
          entity: 'cravesReasoned',
          userId: user.id,
          params: { lat: location?.lat, lng: location?.lng },
        })
      : ['crave', 'user', 'cravesReasoned', null, null],
    queryFn: ({ signal }) => fetchCravesReasoned({ lat: location?.lat, lng: location?.lng, signal }),
    enabled: Boolean(user),
    staleTime: STALE_TIME.normal,
  });
}
