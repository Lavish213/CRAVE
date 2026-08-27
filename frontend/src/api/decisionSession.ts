import { client } from './client';
import { normalizePlaceOut } from './normalize';
import { PlaceOut } from './places';

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
