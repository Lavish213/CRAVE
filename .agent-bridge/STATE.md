# Active agent state

Status: ready-for-review
Owner: Claude
Branch: claude/phase3-authorization-identity (PR to be opened against main)
Base SHA: f4c2870 (main, post-Phase-2 merge -- PR #131)
Commit SHA: ee1de97
Scope: Phase 3 of the canonical CRAVE_PHASES_3_TO_7_PRODUCTION_HARDENING_
EXECUTION_SPEC.md -- Authorization, Identity & Detail Integrity. This
supersedes the earlier informal "Phase 3: main tabs" audit (PR #131,
merged, no findings) -- that was a different, now-closed scope under
the prior 8-phase framing; the uploaded spec is the canonical plan
going forward.
Locked files: none -- handoff complete.

## Outcome

Preflight audit read `taste-profile/[userId].tsx`, `user/[id].tsx`,
`place/[id].tsx`, and the backend profile/taste/ranking/block/follow/
feed routes and services, building the authorization matrix the spec
requires before touching anything. Found and fixed:

- **P0 -- server block/privacy authorization gap** (confirmed, not
  hypothetical: `profile.py`'s own prior docstring said so outright --
  "Block enforcement is handled client-side ... not duplicated here").
  `GET /profile/{user_id}/taste` and `GET /rankings/user/{target_user_id}`
  never checked block status server-side at all; a blocked party
  calling either route directly (bypassing the app's own UI, which does
  hide the Taste Profile link / rankings client-side) could still pull
  the blocking party's full taste stats and ranked list. Both routes now
  call `block_service.is_blocked` (already symmetric by design) and
  return 403 for a blocked relationship. `follow_service`/
  `friend_rankings_service`/`feed_social.py` were checked and are
  already block-safe by construction (a block tears down any existing
  follow both directions, and those surfaces are follow-graph-derived)
  -- verified-healthy, left untouched.
- **P0 -- owner locked out of their own private profile/taste/rankings**
  (confirmed, reachable via `profile.tsx`'s own "Your Taste Profile"
  button and via tapping your own leaderboard/friend-ranking row):
  `GET /profile/{user_id}`, `GET /profile/{user_id}/taste`, and
  `GET /rankings/user/{target_user_id}` all gated purely on
  `is_public`, with no notion of who was asking -- so a user who set
  their own profile private got "profile not found" viewing their own
  content through these routes. `get_public_profile` now takes an
  optional viewer id and bypasses the `is_public` gate for the owner;
  `get_taste_profile_route` and `get_user_rankings` do the same
  (`get_user_rankings` also had its authenticated caller id discarded
  entirely -- `_user_id`, unused, prefixed to suppress the linter --
  now actually used for both the owner-bypass and the block check).
- **P0 -- Taste Profile identity integrity** (confirmed, matches the
  spec's exact described historical failure): `taste-profile/
  [userId].tsx` never reset `taste`/`blocked` state when a new load
  started, only overwrote them on success. Profile A's taste profile
  loads and renders; navigating to profile B succeeds on the *profile*
  fetch (header correctly updates to B) but B's own taste fetch then
  fails (network/5xx) -- the catch block only ever handled a 404, so
  `taste` was left holding A's stale data, which rendered under B's
  now-correct header. Separately, `load()`'s dependency array was
  `[userId, isSelf]`, missing `me?.id` -- a viewer switch (account A to
  account C) while viewing the *same* target profile never changes
  `isSelf` in either case, so it silently never refetched, leaving
  viewer A's block/taste view showing under viewer C's session. Fixed
  by adopting `user/[id].tsx`'s own already-proven pattern exactly:
  `loadedForIdRef`/`loadedForViewerRef`, reset profile/taste/blocked
  only when the (userId, viewer) pairing actually changes, mark
  "attempted" before the fetch settles (not only on success), and a
  render-time `isStaleForCurrentIdentity` gate closing the one-render
  gap between an identity change and the effect that reacts to it.
- **User Profile error truth**: `user/[id].tsx`'s outer catch only ever
  distinguished a 404 (`notFound`) -- any other failure on the primary
  profile fetch (network, timeout, 5xx) collapsed into the exact same
  "Profile not found. This account doesn't exist, or its list is
  private." EmptyState, with no retry. Added a distinct `profileError`
  state with an `ErrorState`+Retry, leaving the 404 branch (real
  product truth) untouched.
- **Place Detail menu truth**: `place/[id].tsx`'s menu fetch's `.catch()`
  reset `menuItems` to `[]` with no distinguishing flag, so a menu
  fetch failure (network/5xx) rendered the exact same "Menu coming
  soon"/"No menu on file yet" copy a genuinely empty (200, `items: []`)
  menu gets. Extracted the fetch into a stable `loadMenu` callback,
  added a `menuError` state with its own inline retry (place itself
  stays fully usable regardless -- this is a supplementary resource,
  per the spec's own framing).

## Verification

- Frontend: `npx tsc --noEmit` clean. `npx jest` 364/364 passed, 37
  suites (360 baseline + 4 new: 1 in place-detail.test.tsx, 2 in
  taste-profile.test.tsx, 1 in user-profile.test.tsx).
- Backend: `python3 -m pytest -q` 1041 passed, 2 skipped (1029 baseline
  + 12 new in test_social_routes_integration.py). Run locally against
  SQLite -- CI's "Backend (same suite, against real Postgres)" job is
  the actual proof this branch needs before merge, same discipline as
  Phase 2 (this branch's SQL changes are simple `.filter()`/existing
  `is_blocked()` calls, not new query shapes, so lower risk than Phase
  2's dialect-sensitive changes, but not assumed clean without that
  job).

## Known gaps / risks

- Direct API bypass tests cover `GET /profile/{id}`, `GET /profile/
  {id}/taste`, and `GET /rankings/user/{id}` -- the three routes the
  audit actually found unenforced. Did not add near-duplicate tests to
  `follows.py`/`feed_social.py`/`friend_rankings_service` since those
  were verified block-safe by construction (block tears down follows
  both directions; those surfaces only ever read the follow graph) --
  already covered by existing service-level tests
  (`test_block_service.py`, `test_friend_rankings_service.py`).
- The "reverse block direction" and "unblock restores visibility"
  regression cases were exercised on the taste-profile route only, not
  duplicated on rankings -- `is_blocked()` itself is one shared,
  already-unit-tested function; both routes call it identically.
- This phase did not touch Phase 4-7's scope (ranking transaction
  integrity, video/media transaction integrity, telemetry/location/
  async truth, performance/accessibility/security/release
  certification) -- per the spec's own strict ordering, those are
  separate, later phases, each on its own fresh branch.
- Did not add a distinct "401 auth behavior" state to `user/[id].tsx`
  as its own category (spec's User Profile error truth section lists
  it alongside 404/privacy-block/network-5xx) -- `GET /profile/
  {user_id}` doesn't require authentication at all (now takes an
  *optional* viewer id only for the owner-bypass), so a 401 there is
  not reachable in practice; folded into the general `profileError`
  retryable-error bucket instead of building out an unreachable branch.

## Next action

Push this branch, open a narrow PR against main following the spec's
required PR contract (Problem/Verified Root Causes/Scope/Files Changed/
Behavior Before/After/Regression Tests/Full Verification/Security
Impact/Remaining Risks/Explicitly Out of Scope), request CodeRabbit
review, hold to the same three gates Phases 1-2 used (CI green
including the real-Postgres job, review threads resolved, no scope
creep beyond what's recorded here) before merge. After merge, Phase 4
(Ranking Transaction Integrity) is next per the spec's strict ordering
-- not yet claimed, needs its own fresh branch and its own
preflight audit against whatever `main` looks like at that point.
