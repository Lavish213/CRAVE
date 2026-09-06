# H-20260906-phase2-search-discovery

Status: ready-for-review
Owner: Claude
Branch: claude/phase2-search-discovery (PR #130 open against main)
Base SHA: 31f24d2 (main, post-Phase-1 merge -- PR #129)
Commit SHA: 8d51fb8b2a2ace03ccb41c44bf9e2462d995dcd1
Allowed next files: none from me -- this branch is in review, no more
code planned here unless CI/review findings require it.

## Outcome

Two sequential, user-directed frontend-hardening phases, both fully
diagnosed against current code before any fix (not assumed from a
pre-existing audit):

**Phase 1 -- identity isolation (PR #129, merged):** private React Query
cache scoping (`myRankings`/`friends-feed`/`leaderboard` now carry
`user.id`; `authStore.signOut()` now clears the shared `queryClient`),
account-switch/id-change state resets in `profile.tsx` and
`user/[id].tsx` (both previously kept rendering the outgoing identity's
data with no loading indicator), and a real `useLocationStatus()`
lifecycle (`resolving/granted/denied/unavailable`) replacing
`useLocation()`'s collapsed `UserLocation | null` contract.

**Phase 2 -- Search as a discovery system (PR #130, this branch):**
debounce resurrection (clearing the search box didn't cancel a pending
debounce timer), a broken retry button (was a no-op), cuisine/category
search (backend never matched the category taxonomy, only place names),
ranking-before-pagination (SQL pagination was cutting before
post-query enrichment scoring ran, so an enriched winner could never
surface), request cancellation (searchPlaces() now forwards React
Query's AbortSignal), trending's cache rebuilt onto React Query with a
real TTL, analytics impressions now log on actual FlashList viewability
instead of the instant results are retrieved, plus two small carried-
over fixes (Craves failure->empty, Profile Setup availability retry).

CodeRabbit's review of PR #130 found one real functional bug in this
branch's own first draft (the widened search ranking-pool fetch was
silently truncated back to the public 100-row page cap, so any page at
offset>=100 could return empty while `total` still reported real
matches) plus three smaller issues (a weak test assertion, an
undersized touch target, a flaky test, a missing `refresh()` guard) --
all fixed, verified, and replied to on the PR's review threads.

## Verification

- Frontend: `npx tsc --noEmit` -> clean. `npx jest` -> 360/360 passed, 37
  suites (359 baseline + 1 new).
- Backend: `python3 -m pytest -q` -> 1029/1029 passed, 2 skipped (1028
  baseline + 1 new offset>100 regression test), run locally against
  SQLite. CI's "Backend (same suite, against real Postgres)" job is the
  actual proof for the two SQL changes in
  `search_query.py`/`search_engine.py` (a correlated EXISTS category
  match, and a widened/re-sliced candidate pool) -- check that job's
  status on the PR before treating them as dialect-safe.

## Known gaps / risks

- Fuzzy-fallback typo-tolerance (`_fuzzy_fallback_search` in
  `search_query.py`) still only compares against `Place.name`, not
  category names -- a misspelled cuisine that no place's name happens
  to contain won't match. Deliberately left; the primary bug (no
  category matching at all) is fixed.
- The widened ranking candidate pool is capped (`MAX_CANDIDATE_POOL =
  500` in `search_query.py`) -- pagination deeper than that can still
  exclude a result that would win post-enrichment. Accepted, documented
  bound, not a realistic search session.
- PR #130 not yet merged -- do not build on `claude/phase2-search-
  discovery` until it lands on main; claim a fresh branch instead.

## Next action

Codex: nothing here changes any of your own open Production-lane
work -- these two phases are frontend-only plus the two backend
`search_query.py`/`search_engine.py` files. If you want the actual
current PR status/CI state, check GitHub directly (`Lavish213/CRAVE`
PR #130) rather than trusting a snapshot here, since this file is only
updated at phase boundaries, not on every push. Once #130 merges, the
next phase in this program (per the user's direction, not yet claimed)
is the main tabs -- Feed/Map/Craves -- unless you or the user redirect.
