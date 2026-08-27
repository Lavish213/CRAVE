import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  DecisionSessionParams,
  fetchDecisionSession,
} from '../api/decisionSession';
import { useCityStore } from '../stores/cityStore';
import { useLocation } from './useLocation';

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
    queryKey: ['decision-session', params],
    queryFn: () => fetchDecisionSession(params),
    staleTime: 2 * 60 * 1000,
  });
}
