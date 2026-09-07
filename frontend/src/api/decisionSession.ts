import { client } from './client';
import { normalizePlaceOut } from './normalize';
import { PlaceOut } from './places';
import {
  assertRecommendationSurface,
  type RecommendationContext,
} from './recommendationContext';

export type DecisionRole = 'best_fit' | 'safe_bet' | 'wildcard';

export type DecisionReasonCode =
  | 'top_ranked_in_area'
  | 'high_percentile'
  | 'close_by'
  | 'underrated_pick'
  | 'different_cuisine';

export interface DecisionSessionCard {
  place: PlaceOut;
  role: DecisionRole;
  reason_codes: DecisionReasonCode[];
}

export interface DecisionSessionResponse {
  cards: DecisionSessionCard[];
  degraded: boolean;
}

export interface DecisionSessionParams {
  city_id?: string;
  lat?: number;
  lng?: number;
  radius_miles?: number;
}

export function decisionSessionParamsFromContext(
  context: RecommendationContext,
): DecisionSessionParams {
  assertRecommendationSurface(context, 'decision_session');
  return {
    city_id: context.location?.city_id,
    lat: context.location?.lat,
    lng: context.location?.lng,
    radius_miles: context.location?.radius_miles,
  };
}

export async function fetchDecisionSession(
  params: DecisionSessionParams,
): Promise<DecisionSessionResponse> {
  const { data } = await client.get<DecisionSessionResponse>(
    '/api/v1/decision-session',
    { params },
  );
  if (!Array.isArray(data?.cards)) {
    return { cards: [], degraded: true };
  }
  return {
    cards: data.cards.map((card) => ({
      ...card,
      place: normalizePlaceOut(card.place),
    })),
    degraded: Boolean(data.degraded),
  };
}

/**
 * Shared-context adapter for callers that already operate on the canonical
 * recommendation request model. The shipped endpoint and enum values remain
 * unchanged.
 */
export async function fetchDecisionSessionForContext(
  context: RecommendationContext,
): Promise<DecisionSessionResponse> {
  return fetchDecisionSession(decisionSessionParamsFromContext(context));
}
