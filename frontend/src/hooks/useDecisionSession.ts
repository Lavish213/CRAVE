import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  DecisionSessionParams,
  fetchDecisionSession,
} from '../api/decisionSession';
import { useCityStore } from '../stores/cityStore';
import { useLocation } from './useLocation';
import { foundationQueryKey, STALE_TIME } from '../contracts/foundationGate';

const DECISION_RADIUS_MILES = 20;

export function useDecisionSession() {
  const selectedCity = useCityStore((state) => state.selectedCity);
  const userLocation = useLocation();
  const params = useMemo<DecisionSessionParams>(() => ({
    city_id: selectedCity?.id,
    radius_miles: DECISION_RADIUS_MILES,
    ...(userLocation && !selectedCity
      ? { lat: userLocation.lat, lng: userLocation.lng }
      : {}),
  }), [selectedCity?.id, userLocation?.lat, userLocation?.lng]);

  return useQuery({
    queryKey: foundationQueryKey({
      scope: selectedCity ? 'city' : 'session',
      entity: 'decision-session',
      params: {
        city_id: params.city_id,
        lat: params.lat,
        lng: params.lng,
        radius_miles: params.radius_miles,
      },
    }),
    queryFn: ({ signal }) => fetchDecisionSession(params, signal),
    staleTime: STALE_TIME.normal,
  });
}
