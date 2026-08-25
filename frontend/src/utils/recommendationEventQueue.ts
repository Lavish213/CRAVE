// src/utils/recommendationEventQueue.ts
//
// Batches recommendation events (impressions especially -- one per card
// on screen, potentially dozens per scroll) into a single network call
// every few seconds instead of one request per event. Module-level, not
// a hook -- there's nothing screen-scoped about it; every screen in the
// app logging into the same queue is the point (it's what lets a later
// analysis reconstruct "shown in Feed, then clicked" across screens).
import {
  RecommendationEventInput,
  sendRecommendationEvents,
} from '../api/recommendationEvents';

const FLUSH_INTERVAL_MS = 4000;
// A Feed page is page_size=40 impressions in one shot -- flush
// immediately once a batch reaches that scale rather than waiting out
// the interval, so a heavy scroll session doesn't build an unbounded
// backlog between timer ticks.
const MAX_QUEUE_SIZE = 40;

// One id per app session (cold start to cold start), not per screen —
// lets a later analysis reconstruct "shown in Feed, then clicked, in
// the same session" across screens/tabs. Not persisted: a fresh app
// launch is a fresh session, which is the intended granularity.
const sessionId = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;

let queue: RecommendationEventInput[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;

function flush(): void {
  if (queue.length === 0) return;
  const batch = queue;
  queue = [];
  // Best-effort -- a lost batch is a gap in analytics, not a lost user
  // action, so this doesn't get the offline-outbox/retry treatment
  // cravesStore's addSave/removeSave get.
  sendRecommendationEvents(batch).catch((err) => {
    if (__DEV__) console.warn('[recommendationEventQueue] flush_failed', err?.message);
  });
}

function scheduleFlush(): void {
  if (flushTimer) return;
  flushTimer = setTimeout(() => {
    flushTimer = null;
    flush();
  }, FLUSH_INTERVAL_MS);
}

/** Queues a single recommendation event (session_id is attached automatically). */
export function logRecommendationEvent(
  event: Omit<RecommendationEventInput, 'session_id'>,
): void {
  queue.push({ ...event, session_id: sessionId });
  if (queue.length >= MAX_QUEUE_SIZE) {
    if (flushTimer) {
      clearTimeout(flushTimer);
      flushTimer = null;
    }
    flush();
  } else {
    scheduleFlush();
  }
}

/** Queues several events at once (e.g. every card in a just-loaded Feed page). */
export function logRecommendationEvents(
  events: Array<Omit<RecommendationEventInput, 'session_id'>>,
): void {
  events.forEach(logRecommendationEvent);
}
