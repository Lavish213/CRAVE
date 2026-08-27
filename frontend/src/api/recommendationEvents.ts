// src/api/recommendationEvents.ts
//
// Recommendation Ledger, write side (see backend's
// app/db/models/recommendation_event.py for the full rationale): what
// got shown, where, and what the user did about it -- captured now, so
// a future ranking/personalization model has real data to evaluate
// against instead of starting blind.
import { client } from './client';

export type RecommendationSurface = 'feed' | 'search' | 'map' | 'trending' | 'craves' | 'place_detail' | 'decision_session';
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
  // Idempotency key for a confirmed save/unsave outcome -- see
  // cravesStore.ts's _logSaveOutcome and the backend's
  // RecommendationEvent.client_event_id docstring. A resubmission (the
  // offline outbox retrying after a process kill lands between "queue
  // entry removed in memory" and "removal persisted to disk") reuses the
  // same id, so the server can no-op the duplicate instead of double-
  // counting a confirmed outcome.
  client_event_id?: string | null;
  // A single search interaction session -- narrower than session_id
  // above (which spans a whole app launch). See search.tsx's
  // searchSessionIdRef for how it's minted; only meaningful when
  // surface='search'.
  search_session_id?: string | null;
  /** Present only for events emitted by the three-card Decision Session. */
  decision_role?: 'best_fit' | 'safe_bet' | 'wildcard' | null;
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
