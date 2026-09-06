# Active agent state

Status: in-progress
Owner: Codex
Branch: codex/phase6-telemetry-location-async
Base SHA: 9ce1da834483bf7792d616f12527b683507b44b8 (main, post-Phase-5 squash merge -- PR #134)
Scope: Phase 6 of `CRAVE_PHASES_3_TO_7_PRODUCTION_HARDENING_EXECUTION_SPEC.md` -- Telemetry, Location & Async Truth.

## Locked scope

6A. Re-verify Feed/Search/Map/Craves recommendation exposure semantics and change only confirmed retrieved-vs-exposed violations.
6B. Audit recommendation-event durability and separate disposable telemetry from high-value learning signals without duplicating already-durable save/rank persistence.
6C. Define and implement an explicit location freshness policy appropriate to existing consumers while preserving the Phase-1 lifecycle contract.
6D. Re-verify permission recovery semantics; modify only confirmed inconsistent/blocked flows within Phase-6 scope.
6E. Sweep high-value screens for failure-to-empty/not-found/idle truth violations, preserving already-fixed Phase-2/3 behavior.
6F. Re-verify root/route error recovery and harden only confirmed gaps.

## Preflight findings so far

- Feed still logs `impression` for every item as soon as a React Query page arrives, before filters/viewability. Confirmed retrieved != exposed violation.
- Map still logs `impression` immediately for a bounded slice of every successful fetched feature set. Fetch radius is intentionally 1.6x viewport and clustering occurs after fetch, so offscreen/cluster-hidden candidates can be recorded as impressions. Confirmed retrieved != exposed violation.
- `recommendationEventQueue.ts` is explicitly best-effort: it removes a batch before sending and drops failed sends. Must determine which events are disposable versus already durably represented elsewhere before changing architecture.
- `useLocation.ts` exposes `updatedAt`, but once state is `granted` it remains session-cached and foreground recheck exits immediately. Confirmed freshness gap; implementation must preserve existing denial/unavailable recovery and avoid unnecessary GPS work.

## Files under active audit

- `frontend/app/(tabs)/index.tsx`
- `frontend/app/(tabs)/map.tsx`
- `frontend/app/(tabs)/search.tsx`
- `frontend/app/(tabs)/craves.tsx`
- `frontend/src/utils/recommendationEventQueue.ts`
- `frontend/src/hooks/useLocation.ts`
- related tests and existing save/rank durability paths
- `frontend/app/_layout.tsx` and high-value async screens only if current code confirms remaining truth/recovery gaps

## Rules

- Verify current code before every edit.
- No speculative refactors or product redesign.
- Preserve merged Phase 1-5 behavior.
- Empty is legal only after a successful retrieval returning zero usable records.
- Candidate != impression; retrieved != exposed.
- No new explicit `any` or fabricated identity.
- Full frontend/backend/TypeScript/CI verification before merge.

## Next action

Complete the Phase-6 current-state map and failure ledger, then implement the smallest coherent fixes with regression tests. Do not start Phase 7 until this branch is reviewed and merged.
