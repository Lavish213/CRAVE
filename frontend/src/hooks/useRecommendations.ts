// src/hooks/useRecommendations.ts
//
// Personalized recommendations. `enabled` lets a hidden/feature-flagged
// consumer preserve hook ordering without performing background network work.
import { useQuery } from '@tanstack/react-query';
import { fetchRecommendations } from '../api/places';
import { useAuthStore } from '../stores/authStore';
import { foundationQueryKey, STALE_TIME } from '../contracts/foundationGate';

export function useRecommendations(enabled = true) {
  const user = useAuthStore((s) => s.user);
  const userId = user?.id ?? null;

  return useQuery({
    queryKey: userId
      ? foundationQueryKey({ scope: 'user', entity: 'recommendations', userId, params: { limit: 20 } })
      : ['crave', 'user', 'recommendations', 'signed-out'],
    queryFn: ({ signal }) => fetchRecommendations(20, signal),
    enabled: enabled && Boolean(userId),
    staleTime: STALE_TIME.normal,
  });
}
