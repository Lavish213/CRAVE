# H-20260906-phase3-authorization-identity

Status: ready-for-review
Owner: Claude
Branch: claude/phase3-authorization-identity (PR to be opened against main)
Base SHA: f4c2870 (main HEAD this branch forked from -- the Phase 3
Feed/Map/Craves audit, PR #131, itself a no-op diff on top of eb55d10,
the actual Phase 2 merge, PR #130)
Commit SHA: 7ffb8e5
Allowed next files: none from me -- this branch is in review, no more
code planned here unless CI/review findings require it.

## Outcome

Phase 3 of the canonical `CRAVE_PHASES_3_TO_7_PRODUCTION_HARDENING_
EXECUTION_SPEC.md` (Authorization, Identity & Detail Integrity),
following Phase 1 (identity isolation, #129, merged) and Phase 2
(Search discovery, #130, merged). This spec supersedes the informal
8-phase framing from earlier in this session -- the prior "Phase 3:
main tabs" audit (#131, merged) found nothing and is a closed, separate
scope; this is a fresh phase under the new canonical plan.

Preflight audit built the required authorization matrix by reading
`taste-profile/[userId].tsx`, `user/[id].tsx`, `place/[id].tsx`, and the
backend profile/taste/ranking/block/follow/feed routes and services.
Found and fixed, each re-verified against current code before touching
anything (not assumed from the spec's own framing):

1. **Server block/privacy authorization gap (P0)** -- `GET /profile/
   {user_id}/taste` and `GET /rankings/user/{target_user_id}` never
   checked block status server-side; a blocked party calling either
   route directly could still pull the blocking party's full taste
   stats/ranked list, bypassing the app's own client-side hiding of
   those links. Both now call the existing (already symmetric)
   `block_service.is_blocked` and return 403.
2. **Owner locked out of their own private profile/taste/rankings
   (P0)** -- all three routes gated purely on `is_public` with no
   viewer awareness, so a user with a private profile got "profile not
   found" viewing their *own* content (reachable via their own "Your
   Taste Profile" button, or their own leaderboard/friend-ranking row).
   `get_public_profile` now takes an optional viewer id and bypasses
   `is_public` for the owner; `get_taste_profile_route`/
   `get_user_rankings` do the same (`get_user_rankings` also had its
   authenticated caller id silently discarded -- now used for both the
   owner-bypass and the block check).
3. **Taste Profile identity integrity (P0)** -- matches the spec's
   exact described historical failure: A's taste renders; navigating to
   B succeeds on the profile fetch but B's own taste fetch fails, and
   A's stale taste data rendered under B's now-correct header (the
   catch block only ever handled a 404, never reset `taste`). Separately,
   a viewer switch with the same target profile never refetched (`isSelf`
   unchanged in both cases, and `me?.id` wasn't in `load()`'s deps).
   Fixed by adopting `user/[id].tsx`'s own already-proven
   `loadedForIdRef`/`loadedForViewerRef` + render-time stale-gate
   pattern exactly.
4. **User Profile error truth** -- `user/[id].tsx` collapsed any
   non-404 failure (network/timeout/5xx) into the same "Profile not
   found" copy as a real 404, with no retry. Added a distinct
   `profileError` state with `ErrorState`+Retry.
5. **Place Detail menu truth** -- a menu fetch failure rendered the
   same "Menu coming soon"/"No menu on file yet" copy a genuinely empty
   menu gets. Added a distinct `menuError` state with its own inline
   retry; the place page itself stays fully usable either way.

`follow_service`/`friend_rankings_service`/`feed_social.py` were
checked and are already block-safe by construction (a block tears down
any existing follow both directions; those surfaces are purely
follow-graph-derived) -- verified-healthy, left untouched.

CodeRabbit's first-pass review found one real functional bug in this
branch's own first draft: `accessError`/`profileError`/`notFound` were
only ever cleared inside the identity-change reset block (alongside
`profile`/`taste`/`loading`), so a same-identity retry that actually
succeeded still rendered the stale error screen over freshly-fetched
good data. Fixed by splitting the block -- data/loading stay identity-
gated (preserves the deliberate no-flash-on-same-identity-refocus
behavior `user/[id].tsx` already had before this phase), outcome flags
now clear on every attempt. Also corrected two handoff-record
inaccuracies it caught: a mislabeled PR number (this file said `f4c2870`
was itself "the Phase 2 merge, PR #131" -- it's PR #131's own no-op
audit commit; the real Phase 2 merge is `eb55d10`, PR #130), and a
wrong claim that a 401 can't reach `GET /profile/{user_id}` (it can,
via the separate `require_api_key` route dependency, not the optional
viewer-identity one) -- both fixed, the 401 claim backed by a new
regression test proving it already routes through the existing
`profileError` bucket correctly.

## Verification

- Frontend: `npx tsc --noEmit` -> clean. `npx jest` -> 367/367 passed,
  37 suites (360 baseline + 7 new -- includes the CodeRabbit-driven
  retry-recovery and 401-routing tests).
- Backend: `python3 -m pytest -q` -> 1041 passed, 2 skipped (1029
  baseline + 12 new in `test_social_routes_integration.py`), run
  locally against SQLite. CI's "Backend (same suite, against real
  Postgres)" job is the actual proof for this branch, same discipline
  as Phase 2 -- check that job's status on the PR before treating the
  new `is_blocked()` calls as dialect-safe (lower risk than Phase 2's
  changes: no new query shapes, just existing filters/an existing
  service call, but not assumed clean without that job).

## Known gaps / risks

- Direct-API-bypass tests cover the three routes the audit actually
  found unenforced (`GET /profile/{id}`, `GET /profile/{id}/taste`,
  `GET /rankings/user/{id}`) -- not duplicated onto
  `follows.py`/`feed_social.py`/`friend_rankings_service`, which were
  verified block-safe by construction and already have their own
  service-level test coverage.
- Did not build out a distinct "401 auth behavior" state for
  `user/[id].tsx` -- a 401 there (reachable via `require_api_key`, see
  above) already falls into the general `profileError` retryable-error
  bucket like any other non-404 failure; there's nothing meaningfully
  different for this screen to do with it, since the app doesn't manage
  `x-api-key` as a user-facing credential.
- Phases 4-7 (ranking transaction integrity, video/media transaction
  integrity, telemetry/location/async truth, performance/accessibility/
  security/release certification) are untouched -- per the spec's
  strict ordering, each is its own later phase on its own fresh branch.

## Next action

Codex: this branch touches `backend/app/api/v1/routes/profile.py`,
`backend/app/api/v1/routes/rankings.py`, and three frontend detail
screens (`taste-profile/[userId].tsx`, `user/[id].tsx`,
`place/[id].tsx`) plus their tests -- check for conflicts if you're
touching any of those. Once this merges, Phase 4 (Ranking Transaction
Integrity) is next per the spec, not yet claimed -- needs its own fresh
preflight audit against whatever `main` looks like at that point, not
assumed from this note.
