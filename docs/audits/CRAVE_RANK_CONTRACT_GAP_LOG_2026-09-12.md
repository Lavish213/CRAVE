# Rank Contract Gap Log — 2026-09-12

Scope: Rank only, no redesign. Base: `origin/main` at `7bf81bd`.

| Severity | Gap | Root cause | Files | Status |
| --- | --- | --- | --- | --- |
| P0 | A direct `/rank/{placeId}` entry could start Rank without declared/verified visit evidence. | Eligibility was enforced only when building Rank Home's queue, not at the write boundary. | `backend/app/api/v1/routes/rankings.py`, `backend/app/services/visit_evidence_service.py`, `backend/tests/test_rank_queue.py` | Fixed: write boundary requires server-held declared/verified evidence and uses its timestamp; inferred-only evidence returns 403. |
| P1 | Rank Home could display the genuine-empty state when one request failed and the other returned empty. | Empty-state check ignored query error state. | `frontend/app/rank-home.tsx`, `frontend/__tests__/rank-home.test.tsx` | Fixed. Partial failure remains explicit and retryable. |
| P1 | Rank Home account data used ad-hoc keys/default freshness and did not forward cancellation. | Rank predated Foundation query contracts. | `frontend/app/rank-home.tsx`, `frontend/src/api/rankHome.ts`, `frontend/src/api/social.ts` | Fixed with deterministic Foundation user keys, account id, short stale class, and AbortSignal forwarding. |
| P1 | Completing Rank could leave queue/list caches stale. | Ranking workflow did not invalidate its remote read models. | `frontend/app/rank/[placeId].tsx` | Fixed: both account-scoped caches invalidate only after a confirmed result. |
| P1 | An expired/tampered comparison left the user retrying a permanently dead token. | All comparison failures shared the same stay-in-place path. | `frontend/app/rank/[placeId].tsx`, `frontend/__tests__/rank-place.test.tsx` | Fixed: token is discarded and the existing tier stage restarts with explicit copy. PR #257's backend tamper test remains green. |
| P1 | A prior-account/route request could release the current submission lock in `finally`. | Generation checks guarded result/error writes but not lock cleanup. | `frontend/app/rank/[placeId].tsx` | Fixed; account changes now also reset the workflow generation. |
| P1 | Share failures and unsupported devices were silent. | Best-effort catch intentionally swallowed a user-actionable failure. | `frontend/app/rank/[placeId].tsx` | Fixed with visible retry guidance. |
| P2 | “See my list” routed to Profile instead of Rank Home. | Historical route was never corrected. | `frontend/app/rank/[placeId].tsx`, `frontend/__tests__/rank-place.test.tsx` | Fixed. |
| P1 | Automatic `ranked_place` activity creation and public-profile full-list APIs remain legacy social behavior. | Existing Profile/Feed architecture treats a public profile as opt-in visibility; changing it would reopen the separately sequenced Profile/social and Feed lanes. | `backend/app/api/v1/routes/rankings.py`, `frontend/app/user/[id].tsx` | Deferred; requires the controlling Profile/social privacy contract. This Rank PR does not expand the behavior or add new signals. |
| P1 | Rank's image export does not carry a universal place link. | `expo-sharing` shares the generated file but has no cross-platform message/link attachment contract. | `frontend/app/rank/[placeId].tsx` | Deferred; Foundation universal-link routing/associated-domain release work must land before changing the approved share artifact. Failure handling is fixed here. |
| P2 | No device E2E exists for Rank comparison completion, large text, screen reader, or offline transition. | Repository E2E baseline remains a single smoke file. | `frontend/e2e/` | Deferred; requires device/simulator infrastructure. Existing controls retain labels/roles and 44px+ targets. |

## Re-verified historical items

- PR #258 shared `AuthGateHost` / `requestAuthGate` integration remains present for Rank Home and `/rank/[placeId]`; it was not rebuilt.
- PR #257's tampered-token regression remains present and passes in the focused backend suite.
- Existing HTTP integration tests now create explicit visit evidence instead of bypassing the production eligibility contract.
- Comparison tokens remain signed, user-bound, short-lived, and final comparison replay remains idempotent.
- Rank remains comparison-based and does not compute position client-side or introduce confidence/taste claims.
