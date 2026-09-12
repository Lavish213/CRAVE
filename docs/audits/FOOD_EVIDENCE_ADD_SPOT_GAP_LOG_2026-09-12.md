# Food Evidence / Add Spot gap log — 2026-09-12

Authority: `docs/doctrine/CRAVE_FRONTEND_EXECUTION_ORDER.md`. Base `7bf81bd`.
This lane hardened existing integration boundaries; it did not redesign them.

| Severity | Root cause and location | Status |
| --- | --- | --- |
| P1 | A routed draft ID was selected without verifying its owner; store mutations also trusted the caller. `frontend/app/add-spot.tsx`, `frontend/src/stores/postingDraftStore.ts` | Fixed with account-scoped selection and owner checks; regression coverage added. |
| P1 | Navigation could leave Add Spot before media attachment finished, hiding failed writes and their retry path. Same files. | Fixed: attachment is awaited, successful attachment gates Place Detail navigation, and failed drafts remain visibly retryable. |
| P2 | React state alone did not synchronously prevent rapid duplicate capture completion; camera/library promise failures could be hidden. `frontend/app/food-evidence.tsx` | Fixed with an in-flight guard and user-visible failure handling. |
| P2 | Candidate and media retry idempotency required verification. Posting draft store and backend discovery promotion services. | Verified: draft outcome transitions prevent concurrent attachment; candidate corroboration and canonical-place promotion dedupe writes. Backend unchanged. |
| P2 | Location denial has no approved location-free/manual Add Spot contract. | Deferred: adding Search/Map or unfinished Posting V2 behavior would cross the locked lane boundary. Existing retry and OS Settings paths remain intact. |
| P2 | Anonymous drafting conflicts with the current merged owner-at-capture boundary. | Deferred pending an approved ownership/migration contract. |
| P2 | Current main has no trustworthy full composer/private-log visit emission. | Capability-gated: no fabricated visit, Dish entity, taste signal, Rank eligibility, or analytics event was added. |
| P3 | Nearby search is workflow state rather than TanStack Query state. | No change: coordinates/permission are ephemeral and existing run/account generation guards prevent stale or cross-account UI writes. |

Backend review found authenticated, API-keyed, rate-limited nearby endpoints with
bounded coordinate/name validation and minimal candidate-status disclosure. No
backend contract defect requiring a change was found.
