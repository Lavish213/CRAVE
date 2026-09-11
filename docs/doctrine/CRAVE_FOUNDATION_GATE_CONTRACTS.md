# CRAVE Foundation Gate Contracts

Status: **LOCKED FOUNDATION CONTRACTS**  
Date: 2026-09-11  
Scope: error taxonomy, React Query conventions, universal-link contract,
privacy/provenance scopes.

This document finishes the contract portion of the Foundation Gate created by
`CRAVE_FRONTEND_EXECUTION_ORDER.md`. It intentionally locks interfaces and
invariants, not a speculative rewrite of every screen. Future vertical slices
must import/obey these contracts when they touch a screen.

Executable companion: `frontend/src/contracts/foundationGate.ts`.

## Sources checked

- TanStack Query official docs: query keys, important defaults, cancellation.
- Expo Router official docs: linking and universal/deep-link behavior.
- React Native official docs: `Linking`/accessibility behavior.
- Apple developer docs: associated domains / universal links expectations.
- W3C/WCAG and OWASP privacy guidance: avoid color-only/status-only truth,
  preserve user intent, data minimization, consent, and access control.

## 1. Error taxonomy

Every user-visible failure must map to exactly one `ErrorKind`:

| Kind | Meaning | UX requirement |
| --- | --- | --- |
| `offline` | Device/network unavailable | Preserve input/context; retry later. |
| `timeout` | Backend did not answer in time | Retry affordance; preserve input/context. |
| `unauthorized` | User must sign in | Use auth gate / `PendingIntent`; no dead-end toast. |
| `forbidden` | Signed-in user lacks permission | Explain access problem; no blind retry loop. |
| `not_found` | Entity missing/removed/expired | Controlled full state. |
| `rate_limited` | Too many requests | Wait-and-retry copy; no repeated hammering. |
| `server_error` | Backend/system fault | Honest “on us” copy + retry. |
| `invalid_data` | User input/request is not acceptable | Inline correction path. |
| `cancelled` | Newer request replaced this one | Silent telemetry only. |
| `unknown` | Unclassified fallback | Retry if safe; classify later. |

Rules:

- `401` must never be handled as a generic error if the action can be resumed;
  it routes through the auth gate.
- Cancelled/aborted requests do not show user-facing errors.
- Empty state and error state are distinct. A failed fetch must not silently
  render “nothing here yet.”
- Every `catch {}` / `.catch(() => {})` must be classified as:
  `ignorable_cleanup`, `recoverable_background`, `user_actionable`, or
  `invariant`.

## 2. React Query conventions

CRAVE does **not** migrate all routes mechanically. A route migrates when its
slice is audited/finalized. When a route does migrate:

- Query keys use `foundationQueryKey()` or the same shape:
  `['crave', scope, entity, userIdOrNull, stableParamsOrNull]`.
- User-scoped server state must include `userId`.
- Query parameters must be serializable, deterministic, and include every
  variable the query function depends on.
- Query functions must accept and pass `AbortSignal` to HTTP clients whenever
  the underlying client supports cancellation.
- Account switch/sign-out clears the shared query client; user-specific query
  keys must still include user id so stale data cannot cross accounts before
  clear completes.
- Default stale-time class is explicit:
  - `realtime`: `0`
  - `short`: `60s`
  - `normal`: `2m`
  - `long`: `10m`
  - `static`: `60m`
- Error presentation comes from the error taxonomy above; each screen can
  localize copy, but cannot change the semantic class silently.

## 3. Universal-link contract

`https://crave.app/...` is the primary external link. `crave://...` remains a
native fallback/internal compatibility scheme.

Required destination behavior:

| Destination | Primary URL | Fallback scheme | Auth |
| --- | --- | --- | --- |
| Place | `https://crave.app/place/{id}` | `crave://place/{id}` | public read; gated actions after open |
| Rank | `https://crave.app/rank/{placeId}` | `crave://rank/{placeId}` | auth-gated, preserves intent |
| Profile | `https://crave.app/user/{id}` | `crave://user/{id}` | depends on profile visibility |

Rules:

- App installed: open exact destination.
- App not installed: HTTPS route must have a useful web fallback or controlled
  fallback page, not a dead scheme link.
- Signed-out gated destination: create a `PendingIntent`, show auth gate, and
  resume safely after sign-in.
- Malformed/old link: route to a controlled fallback state; never crash.
- Coverage required before release: cold start, warm start, backgrounded,
  terminated, signed-out, and malformed links.

## 4. Privacy/provenance scopes

Privacy scope and data provenance are separate axes. Source credibility does
not grant display permission.

Privacy scopes:

| Scope | Display rule |
| --- | --- |
| `private` | Owner only. |
| `shareable` | May be displayed to allowed viewers. |
| `display_identity` | Public/profile identity data. |
| `explicit_opt_in` | Only after explicit user opt-in. |

Provenance stamp required for factual place fields that can become stale or
contested:

```ts
{
  source: 'user' | 'friend' | 'restaurant' | 'osm' | 'overture' |
          'google_places' | 'menu_provider' | 'system_inferred' | 'unknown',
  fetchedAt: string | null,
  confidence: 'verified' | 'high' | 'medium' | 'low' | 'unknown',
  privacyScope: PrivacyScope
}
```

Rules:

- Hours, menu, image, outdoor seating, and restaurant correction data must not
  render with more certainty than their provenance supports.
- `fetchedAt === null` means freshness is unknown; copy must not imply “just
  verified.”
- `system_inferred` taste/profile data defaults private unless explicitly
  moved to another scope.
- Visibility, recommendation influence, and factual retention remain separate
  axes. A privacy toggle must never imply deletion or taste reset unless it
  performs that mutation explicitly.

## 5. What is now complete vs. still implementation work

Complete at Foundation Gate:

- Auth-gate/PendingIntent sweep from PR #258.
- Error taxonomy contract.
- React Query key/cancellation/staleness/account-isolation contract.
- Universal-link destination contract.
- Privacy/provenance scope contract.
- Executable TypeScript helpers/tests for the above contracts.

Still implementation work for later slices:

- Migrating specific routes to TanStack Query.
- Building associated domains/web fallback for HTTPS universal links.
- Rendering provenance-aware hours/menu/image copy in Place Detail.
- Classifying every existing `catch {}` site while touching that slice.
- Adding E2E coverage journey-by-journey.

Next frontend lane after this contract is merged: **Place Detail proving
slice**, per `CRAVE_FRONTEND_EXECUTION_ORDER.md`.
