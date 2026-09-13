# Food Evidence / Add Spot gap log — 2026-09-12

Authority: `docs/doctrine/CRAVE_FRONTEND_EXECUTION_ORDER.md`. Base:
`7bf81bda3dab274f00ec5db35c68c8235f7a3c2f` (`origin/main`). This was a
hardening/integration audit, not a redesign.

| Severity | Finding / root cause | Path | Status |
| --- | --- | --- | --- |
| P1 | A route `draftId` selected a persisted draft without checking its `ownerId`; after account switch, another account could display and attempt to attach that local media. Store mutations also trusted callers to enforce ownership. | `frontend/app/add-spot.tsx`, `frontend/src/stores/postingDraftStore.ts` | Fixed: selector and both place/candidate mutations require the active owner; regression tests added. |
| P1 | Existing-place navigation happened before attachment completed. A failed write left a durable failed draft, but the journey had already left the only attachment surface and exposed no retry. | `frontend/app/add-spot.tsx`, `frontend/src/stores/postingDraftStore.ts` | Fixed: attachment is awaited, navigation occurs only after success, failed place attachments are explicitly retryable, and saved-media recovery copy remains visible. |
| P2 | Rapid capture completions could create more than one durable draft because React's `saving` state does not synchronously guard event handlers. Picker/camera promise rejections were also unhandled outside draft persistence. | `frontend/app/food-evidence.tsx` | Fixed: synchronous in-flight guard plus visible camera/library errors. |
| P2 | Candidate and media retries needed idempotency verification. | `frontend/src/stores/postingDraftStore.ts`, `backend/app/services/discovery/candidate_store_v2.py`, `backend/app/services/discovery/promote_service_v2.py` | Verified: draft outcome transition prevents concurrent attachments; candidate corroboration keys dedupe the same user; promotion resolves against canonical places. Backend unchanged. |
| P2 | Location denial has no location-free/manual restaurant search path. Current approved Add Spot is explicitly a tight-radius GPS flow; the newer posting contract is still draft/YELLOW and importing Search/Map would cross the locked lane boundary. | `frontend/app/add-spot.tsx`, `docs/doctrine/CRAVE_SCREEN_CONTRACT_NATIVE_POSTING.md` | Deferred: requires an approved contract and a dedicated compatibility slice, not an unreviewed redesign here. Existing request-again and OS Settings flows are verified. |
| P2 | Food Evidence requires sign-in before capture, while the draft native-posting contract proposes anonymous drafting and auth-at-publish. The current merged Posting V2-A boundary deliberately requires an owner at capture time. | `frontend/app/food-evidence.tsx`, `docs/doctrine/CRAVE_SCREEN_CONTRACT_NATIVE_POSTING.md` | Deferred: preserve current production boundary until anonymous draft ownership/migration is approved and implemented end to end. |
| P2 | Full composer/private-log publish semantics and visit-evidence emission are not present on current `main`; therefore this lane cannot truthfully claim a persisted visit or unlock Rank eligibility. | `frontend/app/food-evidence.tsx`, `frontend/app/add-spot.tsx` | Correctly capability-gated/deferred. This flow captures media and identifies a restaurant only; no fabricated visit, Dish entity, taste signal, or analytics event was added. |
| P3 | Add Spot remote search remains a short-lived workflow request rather than TanStack Query state. | `frontend/app/add-spot.tsx` | No change: location permission and coordinates are ephemeral workflow state; run-id cancellation and account-generation guards already prevent stale overwrites/cross-account UI writes. |

Backend review confirmed `/nearby/search`, `/nearby/confirm`, and candidate
status require API key, authenticated user, and rate limiting; validation
bounds coordinates and names. Candidate status exposes only an unguessable ID,
resolution flags, and canonical place ID. No backend contract defect requiring
a change was found.
