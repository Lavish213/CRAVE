// src/utils/errorMessage.ts
//
// Shared error-copy classification. This used to reimplement its own
// 429/offline detection independently of cravesStore.ts's private
// `_classifyError` and place/[id].tsx's own inline copy of the same
// check -- three near-identical classifiers that had already drifted from
// each other. The actual classification decision (what kind of error this
// is) now comes from the single, already-tested Foundation Gate taxonomy
// in ../contracts/foundationGate.ts; this function keeps its existing
// simple string-returning API (callers pass a caller-specific fallback
// message and get back either that fallback or one of the two
// app-established, already-shipped copy strings below) so nothing that
// already calls errorMessageFor has to change, and no existing copy in
// the running app changes either -- only where the kind determination
// comes from.
import { classifyHttpStatus } from '../contracts/foundationGate';

export function errorMessageFor(err: unknown, fallback: string): string {
  const hasResponse = Boolean((err as { response?: unknown } | null | undefined)?.response);
  const status = (err as { response?: { status?: number } } | null | undefined)?.response?.status;

  // No response at all means the request never reached the backend --
  // Foundation Gate's own 'offline' kind, distinct from a real 4xx/5xx.
  const kind = hasResponse ? classifyHttpStatus(status) : 'offline';

  if (kind === 'rate_limited') return "You're doing that too fast — wait a moment and try again.";
  if (kind === 'offline') return "Can't reach CRAVE — check your connection.";
  return fallback;
}
