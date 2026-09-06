// src/utils/recommendationEventQueue.ts
//
// Recommendation telemetry has two durability classes:
//
// - impressions/clicks are best-effort observational telemetry. Losing an
//   occasional batch is an analytics gap, not lost user state.
// - confirmed save/unsave outcomes are explicit preference signals and carry
//   a server-deduped client_event_id. Those are persisted to a small,
//   account-owned AsyncStorage outbox until the server acknowledges them.
//
// Ranking itself is already persisted transactionally by the ranking backend
// and its recommendation event is server-originated, so it does not need a
// second client outbox here.
import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  RecommendationEventInput,
  sendRecommendationEvents,
} from '../api/recommendationEvents';
import { supabase } from '../lib/supabase';

const FLUSH_INTERVAL_MS = 4000;
const RETRY_INTERVAL_MS = 15_000;
const MAX_QUEUE_SIZE = 40;
const DURABLE_STORAGE_KEY = '@crave/recommendation-event-outbox/v1';

// Analytics correlation only, never an auth/security token. A per-process
// timestamp is sufficient and avoids weak-randomness scanners treating this
// identifier like a security primitive.
const sessionId = `session_${Date.now().toString(36)}`;

interface DurableEnvelope {
  ownerUserId: string;
  event: RecommendationEventInput;
}

let volatileQueue: RecommendationEventInput[] = [];
let durableQueue: DurableEnvelope[] = [];
let durableHydrated = false;
let hydratePromise: Promise<void> | null = null;
let flushTimer: ReturnType<typeof setTimeout> | null = null;
let flushInProgress = false;
let activeFlushPromise: Promise<void> | null = null;

function isDurableOutcome(event: RecommendationEventInput): boolean {
  return (
    (event.event_type === 'save' || event.event_type === 'unsave') &&
    typeof event.client_event_id === 'string' &&
    event.client_event_id.length > 0
  );
}

async function currentUserId(): Promise<string | null> {
  try {
    const { data } = await supabase.auth.getSession();
    return data.session?.user.id ?? null;
  } catch {
    return null;
  }
}

function isValidDurableEnvelope(value: unknown): value is DurableEnvelope {
  if (!value || typeof value !== 'object') return false;
  const envelope = value as Partial<DurableEnvelope>;
  if (typeof envelope.ownerUserId !== 'string' || envelope.ownerUserId.length === 0) return false;
  if (!envelope.event || typeof envelope.event !== 'object') return false;
  const event = envelope.event as Partial<RecommendationEventInput>;
  return (
    typeof event.surface === 'string' &&
    (event.event_type === 'save' || event.event_type === 'unsave') &&
    typeof event.client_event_id === 'string' &&
    event.client_event_id.length > 0
  );
}

async function persistDurableQueue(): Promise<void> {
  try {
    if (durableQueue.length === 0) {
      await AsyncStorage.removeItem(DURABLE_STORAGE_KEY);
      return;
    }
    await AsyncStorage.setItem(DURABLE_STORAGE_KEY, JSON.stringify(durableQueue));
  } catch (err) {
    if (__DEV__) {
      console.warn('[recommendationEventQueue] persist_failed', err instanceof Error ? err.message : err);
    }
  }
}

async function hydrateDurableQueue(): Promise<void> {
  if (durableHydrated) return;
  if (hydratePromise) return hydratePromise;

  hydratePromise = (async () => {
    try {
      const raw = await AsyncStorage.getItem(DURABLE_STORAGE_KEY);
      if (!raw) return;
      const parsed: unknown = JSON.parse(raw);
      if (!Array.isArray(parsed)) return;
      durableQueue = parsed.filter(isValidDurableEnvelope);
    } catch (err) {
      if (__DEV__) {
        console.warn('[recommendationEventQueue] hydrate_failed', err instanceof Error ? err.message : err);
      }
    } finally {
      durableHydrated = true;
      hydratePromise = null;
    }
  })();

  return hydratePromise;
}

function scheduleFlush(delayMs = FLUSH_INTERVAL_MS): void {
  if (flushTimer) return;
  flushTimer = setTimeout(() => {
    flushTimer = null;
    void flushQueues();
  }, delayMs);
}

async function enqueueDurable(
  event: RecommendationEventInput,
  ownerUserIdOverride?: string,
): Promise<void> {
  await hydrateDurableQueue();
  const ownerUserId = ownerUserIdOverride ?? await currentUserId();
  if (!ownerUserId) {
    if (__DEV__) console.warn('[recommendationEventQueue] durable_event_without_owner');
    return;
  }

  const id = event.client_event_id!;
  if (!durableQueue.some((queued) => queued.event.client_event_id === id)) {
    durableQueue.push({ ownerUserId, event });
    await persistDurableQueue();
  }

  if (durableQueue.length >= MAX_QUEUE_SIZE) {
    if (flushTimer) {
      clearTimeout(flushTimer);
      flushTimer = null;
    }
    void flushQueues();
  } else {
    scheduleFlush();
  }
}

async function flushVolatile(): Promise<void> {
  if (volatileQueue.length === 0) return;
  const batch = volatileQueue.splice(0, MAX_QUEUE_SIZE);
  try {
    await sendRecommendationEvents(batch);
  } catch (err) {
    if (__DEV__) {
      console.warn('[recommendationEventQueue] volatile_flush_failed', err instanceof Error ? err.message : err);
    }
  }
}

async function flushDurable(): Promise<boolean> {
  await hydrateDurableQueue();
  if (durableQueue.length === 0) return true;

  const ownerUserId = await currentUserId();
  if (!ownerUserId) return false;

  const ownedBatch = durableQueue
    .filter((queued) => queued.ownerUserId === ownerUserId)
    .slice(0, MAX_QUEUE_SIZE);

  if (ownedBatch.length === 0) return true;

  try {
    await sendRecommendationEvents(ownedBatch.map((queued) => queued.event));
    const acknowledgedIds = new Set(
      ownedBatch.map((queued) => queued.event.client_event_id),
    );
    durableQueue = durableQueue.filter(
      (queued) => !acknowledgedIds.has(queued.event.client_event_id),
    );
    await persistDurableQueue();
    return true;
  } catch (err) {
    if (__DEV__) {
      console.warn('[recommendationEventQueue] durable_flush_failed', err instanceof Error ? err.message : err);
    }
    return false;
  }
}

async function performFlush(): Promise<void> {
  await flushVolatile();
  const durableSucceeded = await flushDurable();

  const ownerUserId = durableQueue.length > 0 ? await currentUserId() : null;
  const hasOwnedDurable = ownerUserId
    ? durableQueue.some((queued) => queued.ownerUserId === ownerUserId)
    : false;

  if (volatileQueue.length > 0 || hasOwnedDurable) {
    scheduleFlush(durableSucceeded ? FLUSH_INTERVAL_MS : RETRY_INTERVAL_MS);
  }
}

function flushQueues(): Promise<void> {
  if (activeFlushPromise) return activeFlushPromise;
  flushInProgress = true;
  activeFlushPromise = performFlush().finally(() => {
    flushInProgress = false;
    activeFlushPromise = null;
  });
  return activeFlushPromise;
}

/**
 * Queues one event and attaches the current app-session id.
 *
 * `durableOwnerUserId` is intentionally optional and ignored for volatile
 * observations. Save/unsave mutation code should pass the userId captured at
 * mutation start so a later account switch cannot change ownership of a
 * confirmed outcome while its network request is still finishing.
 */
export function logRecommendationEvent(
  event: Omit<RecommendationEventInput, 'session_id'>,
  durableOwnerUserId?: string,
): void {
  const attached: RecommendationEventInput = { ...event, session_id: sessionId };

  if (isDurableOutcome(attached)) {
    void enqueueDurable(attached, durableOwnerUserId);
    return;
  }

  volatileQueue.push(attached);
  if (volatileQueue.length >= MAX_QUEUE_SIZE) {
    if (flushTimer) {
      clearTimeout(flushTimer);
      flushTimer = null;
    }
    void flushQueues();
  } else {
    scheduleFlush();
  }
}

/** Queues several observational events using the default classification. */
export function logRecommendationEvents(
  events: Array<Omit<RecommendationEventInput, 'session_id'>>,
): void {
  events.forEach((event) => logRecommendationEvent(event));
}

/** Explicit recovery hook for app-foreground/auth-restoration callers. */
export function flushRecommendationEvents(): Promise<void> {
  if (flushTimer) {
    clearTimeout(flushTimer);
    flushTimer = null;
  }
  return flushQueues();
}

/** Test-only singleton reset. */
export function _resetRecommendationEventQueueForTests(): void {
  if (flushTimer) clearTimeout(flushTimer);
  flushTimer = null;
  volatileQueue = [];
  durableQueue = [];
  durableHydrated = false;
  hydratePromise = null;
  flushInProgress = false;
  activeFlushPromise = null;
}

void hydrateDurableQueue().then(() => {
  if (durableQueue.length > 0) scheduleFlush();
});
