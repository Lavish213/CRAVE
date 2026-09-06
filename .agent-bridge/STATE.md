# Active agent state

Status: ready-for-review
Owner: Claude
Branch: claude/phase2-search-discovery (PR #130 open against main)
Base SHA: 31f24d2 (main, post-Phase-1 merge)
Commit SHA: 2d22b93
Scope: Phase 2 of the user-directed multi-phase frontend hardening
program -- Search as a proper discovery system, plus the two Craves/
Profile Setup bugs Phase 1 diagnosed but deliberately deferred (small,
independently-scoped, riding along only because already fully
diagnosed).
Locked files: none -- handoff complete.

## Outcome

All 10 items (8 confirmed-stack + 2 carried-over), each re-verified
against current code before fixing:

- **Debounce resurrection** (search.tsx): `handleClear()` reset
  query/debouncedQuery but never cancelled the pending debounce timer
  -- text typed just before a clear tap still fired 350ms later and
  resurrected the cleared query. Now clears the timer too.
- **Broken retry** (search.tsx): the error retry button called
  `setDebouncedQuery(query)`, a no-op since they're already equal
  whenever the error fires. Now calls the already-correct,
  already-destructured `refetchSearch`.
- **Cuisine/category search** (backend `search_query.py`): search only
  ever matched `Place.name.ilike(...)` -- a cuisine/category name (e.g.
  "Italian", "sushi") matched nothing unless a place's own name
  happened to contain it. Added a correlated EXISTS match against
  `Category.name` (via `place_categories`), OR'd with the existing name
  match.
- **Near Me/location integration** (search.tsx): migrated from
  `useLocation()` to `useLocationStatus()` -- the screen's own "Searching
  everywhere..." copy now distinguishes still-resolving from a terminal
  denied/unavailable state, previously identical.
- **Trending lifecycle/cache** (`useTrending.ts`): rewritten onto React
  Query (staleTime mirrors backend `trending.py`'s own 5-min
  response-cache TTL) -- was a hand-rolled module-level cache with no
  TTL, the one list hook in the app not already on React Query like
  every sibling screen. Public API unchanged; both real call sites
  (search.tsx, index.tsx) needed no changes.
- **Analytics exposure semantics** (search.tsx): impressions now log
  from FlashList's `onViewableItemsChanged`, not the instant results are
  retrieved -- "retrieved" and "exposed" were conflated. Deduped per
  query via a Set, reset on a genuinely new query.
- **Ranking-before-pagination** (backend `search_engine.py`):
  `search_query.py`'s SQL fetch applies LIMIT/OFFSET using only
  rank_score/distance, but `search_ranker.py`'s exact-match/menu/
  proximity re-scoring runs *after* that -- a result that would win
  post-enrichment could never surface if it didn't already make the
  raw-ordered page window. Widened the candidate fetch (bounded like
  `search_query.py`'s own fuzzy-fallback pool, same tradeoff for the
  same reason -- 500-row cap, +100 padding over offset+limit) so
  enrichment has room to promote a result into the visible page, then
  slices the real page out of the ranked result.
- **Cancellation** (`search.ts`/search.tsx): `searchPlaces()` never
  forwarded React Query's per-query AbortSignal, so a query superseded
  by the next keystroke's debounced fetch kept running its full HTTP
  request to completion. Now threaded through from `queryFn`'s own
  `signal` argument.
- **Craves failure->empty** (craves.tsx): the top-level "true empty"
  gate never checked `cravesError` (already tracked, already correctly
  rendered in the FlashList's own footer) -- a craves-fetch failure with
  zero saves/placeSaves rendered "Start your food memory" instead of
  the error.
- **Profile Setup availability handling** (profile-setup.tsx): the
  username-check's failure path collapsed to `'idle'`, indistinguishable
  from "haven't typed a valid username yet," with no retry (retyping
  the same text never reruns the debounce effect). Added a distinct
  `'error'` state with a working retry affordance.

## Verification

- Frontend: `npx tsc --noEmit` clean; `npx jest` 359 passed, 37 suites
  (340 baseline + 19 new across two commits).
- Backend: full suite 1028 passed, 2 skipped (baseline, unaffected) --
  ran locally against SQLite; the category-name EXISTS join and the
  widened-pool query are standard ANSI SQL with no known SQLite/Postgres
  divergence, but CI's "Backend (same suite, against real Postgres)"
  job is the actual proof for this branch (this exact file previously
  caught a real SQLite-vs-Postgres-only bug -- see its DISTINCT/
  ORDER BY comment -- so it's not assumed clean without that job).

## Known gaps / risks

- Fuzzy-fallback typo-tolerance (`_fuzzy_fallback_search` in
  `search_query.py`) still only compares against `Place.name`, not
  category names -- a genuinely misspelled cuisine (e.g. "italain")
  that no place's name happens to contain won't match. The primary
  confirmed bug (no category matching *at all*, even for exact/
  substring matches) is fixed; typo-tolerance for cuisine names
  specifically is a smaller, separate enhancement, deliberately left.
- The widened ranking candidate pool (500 rows, capped) means very deep
  pagination (beyond roughly page ~16 at a 30-item page size) can still
  have a result that would win post-enrichment excluded if it didn't
  make that pool -- an accepted, documented bound, not a realistic
  search session.
- No PR opened yet.

## Next action

Open a PR, verify CI (frontend + backend/Postgres both need to be
green), request CodeRabbit review, then hold this branch to the same
gates Phase 1 used before merge: CI green, review findings addressed,
and no scope creep beyond what's recorded here.
