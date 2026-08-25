// src/api/recommendationEvents.ts
//
// Recommendation Ledger, write side (see backend's
// app/db/models/recommendation_event.py for the full rationale): what
// got shown, where, and what the user did about it -- captured now, so
// a future ranking/personalization model has real data to evaluate
// against instead of starting blind.
import { client } from './client';

export type RecommendationSurface = 'feed' | 'search' | 'map' | 'trending' | 'craves' | 'place_detail';
export type RecommendationEventType = 'impression' | 'click' | 'save' | 'unsave' | 'rank';

export interface RecommendationEventInput {
  place_id?: string | null;
  surface: RecommendationSurface;
  event_type: RecommendationEventType;
  position?: number | null;
  rank_percentile?: number | null;
  query?: string | null;
  city_id?: string | null;
  session_id?: string | null;
}

export async function sendRecommendationEvents(
  events: RecommendationEventInput[],
): Promise<void> {
  if (events.length === 0) return;
  // Fire-and-forget from the caller's perspective -- this is telemetry,
  // not user-critical state (unlike cravesStore's offline outbox). A
  // dropped batch means a gap in analytics, not a lost user action, so
  // it doesn't need the same retry/backoff treatment.
  await client.post('/api/v1/recommendations/events', { events });
}
