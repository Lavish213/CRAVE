# H-20260906-phase2-search-discovery

Status: merged
Owner: Claude
Branch: both phases now on main -- PR #129 (Phase 1) and PR #130
(Phase 2) merged. This file's own branch (claude/phase2-search-
discovery) is gone post-merge; a Phase 3 audit ran on a separate
branch, claude/phase3-main-tabs, with no diff (see below).
Base SHA: 31f24d2 (main, post-Phase-1 merge -- PR #129)
Commit SHA: eb55d10 (main, post-Phase-2 squash merge -- PR #130)
Allowed next files: none from me -- see "Next action" below.

## Outcome

Two sequential, user-directed frontend-hardening phases, both fully
diagnosed against current code before any fix (not assumed from a
pre-existing audit), both merged to main:

**Phase 1 -- identity isolation (PR #129, merged):** private React Query
cache scoping (`myRankings`/`friends-feed`/`leaderboard` now carry
`user.id`; `authStore.signOut()` now clears the shared `queryClient`),
account-switch/id-change state resets in `profile.tsx` and
`user/[id].tsx` (both previously kept rendering the outgoing identity's
data with no loading indicator), and a real `useLocationStatus()`
lifecycle (`resolving/granted/denied/unavailable`) replacing
`useLocation()`'s collapsed `UserLocation | null` contract.

**Phase 2 -- Search as a discovery system (PR #130, merged):**
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

CodeRabbit's review of PR #130 found one real functional bug in that
branch's own first draft (the widened search ranking-pool fetch was
silently truncated back to the public 100-row page cap, so any page at
offset>=100 could return empty while `total` still reported real
matches) plus three smaller issues (a weak test assertion, an
undersized touch target, a flaky test, a missing `refresh()` guard) --
all fixed, verified, and replied to on the PR's review threads. It also
flagged this repo's own handoff records (STATE.md/this file) for
carrying a stale commit SHA instead of the actual head -- fixed before
merge.

**Phase 3 audit (claude/phase3-main-tabs, no PR -- no diff):** before
claiming Phase 3 (main tabs: Feed/Map/Craves) the same
verify-before-modify way, read all three screens plus their direct
supporting stores/hooks (`cravesStore.ts`, `useRecommendations.ts`,
`useDecisionSession.ts` + its backend route) end to end looking for the
same bug classes Phase 1/2 found elsewhere (private-cache-key leaks,
stale-account-data races, broken retries). Found none -- see
`STATE.md`'s current entry for the per-file detail. These three screens
already carry substantial dedicated hardening from earlier sessions
(account-generation guards, mutation tokens, an offline queue with
backoff, request-id races, map coverage-caching -- see
`CRAVE_REMAINING_WORK.md`'s 2026-08-25/26 entries for that history).
No code changed; nothing to review.

## Verification

- Frontend: `npx tsc --noEmit` -> clean. `npx jest` -> 360/360 passed,
  37 suites (359 baseline + 1 new).
- Backend: `python3 -m pytest -q` -> 1029/1029 passed, 2 skipped (1028
  baseline + 1 new offset>100 regression test), run locally against
  SQLite. CI's "Backend (same suite, against real Postgres)" job
  confirmed green on the merged commit for the two SQL changes in
  `search_query.py`/`search_engine.py` (a correlated EXISTS category
  match, and a widened/re-sliced candidate pool).
- Phase 3 audit: read-only, no test run needed -- no code changed.

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
- No confirmed bug identified in Feed/Map/Craves as of this audit. If
  something surfaces later it should be diagnosed fresh against
  current code, not assumed from this note.

## Next action

Codex: nothing here changes any of your own open Production-lane work.
Both merged phases are frontend-only plus the two backend
`search_query.py`/`search_engine.py` files. The `claude/phase3-main-tabs`
branch exists but is empty (identical to main) -- safe to ignore or
delete. The next phase in this program is genuinely open: the original
8-phase plan's remaining slices are analytics semantics, UX polish,
performance, and a release regression gate, but Feed/Map/Craves (this
audit's target) turned up nothing to fix. If you pick up a next slice,
verify against current code first, the same way this session did --
don't assume this note's absence-of-findings extends to a screen it
didn't actually cover.
