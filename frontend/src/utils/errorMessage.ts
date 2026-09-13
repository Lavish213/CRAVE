// src/utils/errorMessage.ts
//
// Shared error-copy classification (Foundation Gate's error taxonomy --
// see docs/doctrine/CRAVE_FOUNDATION_GATE_CONTRACTS.md's §1). Matches
// cravesStore's own established `_classifyError` shape/copy. Extracted
// here once it was about to be duplicated a third time (SearchScreen.tsx
// and MapScreenCore.tsx each had their own copy) -- every ErrorState call
// site across the app should use this instead of a bare hardcoded string,
// so a 429 or a genuine offline failure never renders the same generic
// "couldn't load" copy client.ts's own axios interceptor already
// classifies more specifically.
export function errorMessageFor(err: unknown, fallback: string): string {
  const status = (err as { response?: { status?: number } } | null | undefined)?.response?.status;
  if (status === 429) return "You're doing that too fast — wait a moment and try again.";
  if (!(err as { response?: unknown } | null | undefined)?.response) {
    return "Can't reach CRAVE — check your connection.";
  }
  return fallback;
}
