# Phase 6 interim progress

Branch: `codex/phase6-telemetry-location-async`
Base: `9ce1da834483bf7792d616f12527b683507b44b8`
Owner: Codex

Confirmed current-code defects:

1. Feed eager page-arrival and Decision Session arrival impressions (`retrieved != exposed`).
2. Map eager fetched-feature impressions despite 1.6x viewport overfetch, filtering, and clustering.
3. Craves manual place-save failure collapses to `[]`; all Craves sections still eager-log fetched data as impressions.
4. Shared granted location remains session-cached indefinitely and does not detect OS permission revocation while backgrounded.
5. Recommendation event queue drops all failed batches, including confirmed save/unsave learning outcomes.
6. Root custom ErrorBoundary Retry merely clears local error state; framework-native SDK55 route retry still needs implementation/verification.

Verified healthy: Search already uses FlashList 50%/250ms viewability with per-query exposure dedupe; preserve it.

Implemented so far:

- shared 5-minute balanced-location freshness + foreground permission revalidation/revocation handling;
- account-owned durable AsyncStorage outbox for confirmed save/unsave telemetry; impression/click remains best-effort; ranking remains server-originated;
- disabled hidden Feed Trending/Recommendations network work behind existing feature flag;
- Feed and Decision Session cards now use one FlashList viewability contract instead of eager retrieval logging.

Still in progress before review-ready:

- Map visible-pin exposure semantics + tests;
- Craves async truth + viewability semantics + tests;
- root SDK55 ErrorBoundary retry;
- blocked-permission sweep (especially Add Spot);
- final async truth re-verification;
- frontend/backend/typecheck/CI stabilization;
- final STATE.md handoff and narrow PR conversion from draft to ready.
