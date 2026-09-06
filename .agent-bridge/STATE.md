# Active agent state

Status: claimed
Owner: Claude
Branch: claude/phase2-search-discovery
Base SHA: 31f24d2 (main, includes Phase 1's merged PR #129)
Commit SHA: (none yet)
Scope: Phase 2 of the user-directed multi-phase frontend hardening
program -- Search only, as a proper discovery system. Explicitly not
combined with Craves or Profile Setup, even though this phase also
carries the fix for the two bugs Phase 1 diagnosed-but-deferred in those
files (Craves failure->empty, Profile Setup availability handling) --
those are small, independently-scoped fixes riding in this PR only
because they were fully diagnosed already, not a scope expansion into
"fix everything." Search Retry (search.tsx) is genuinely in-scope since
it's the same file this phase rebuilds.
Confirmed stack (re-verified against current main before writing this,
not assumed from the earlier diagnosis):
  1. Debounce resurrection -- handleClear() resets query/debouncedQuery
     but never clears the pending debounceRef timer; a timer from text
     typed just before the clear tap still fires and resurrects the
     cleared query.
  2. Broken retry -- onRetry={() => setDebouncedQuery(query)} is a no-op
     (already equal when the error fires); refetchSearch exists and is
     already correctly wired to pull-to-refresh two lines below.
  3. Cuisine/category search -- searchPlaces() never sends category_id
     to the backend at all; search_query.py only does
     Place.name.ilike(search_term), so a cuisine/category typed as a
     query matches nothing unless a place's *name* happens to contain it.
  4. Near Me/location integration -- search.tsx still consumes
     useLocation() (Phase 1's unchanged-signature coords-or-null
     wrapper), not useLocationStatus(), so it can't distinguish
     pending/denied/unavailable/stale -- exactly the "future consumer"
     case Phase 1's PR body flagged.
  5. Trending lifecycle/cache -- useTrending.ts is a hand-rolled
     module-level cache with no TTL, inconsistent with every other list
     screen (search/leaderboard/friends-feed) now on React Query.
  6. Analytics exposure semantics -- search.tsx logs an "impression" the
     instant results arrive (retrieved), not on actual viewability
     (exposed).
  7. Ranking-before-pagination -- search_query.py applies SQL
     LIMIT/OFFSET using only rank_score/distance_sq, then
     search_ranker.py's exact-match/menu-boost re-scoring runs *after*
     that page is already cut -- a result that would win post-enrichment
     can never surface if it didn't make the raw SQL-ordered page window.
  8. Cancellation -- searchPlaces() never passes an abort signal to
     client.get(), so a superseded query can be marked stale by React
     Query but the underlying HTTP request keeps running to completion.
Also carried from Phase 1's deferred list (same file/adjacent scope):
  9. Craves failure->empty (craves.tsx) -- cravesError is tracked and
     rendered correctly in the list footer, but the top-level "true
     empty" gate never checks it.
  10. Profile Setup availability handling (profile-setup.tsx) -- the
      username-check's .catch() collapses to 'idle', indistinguishable
      from "haven't typed yet," no retry path.
Locked files (expected, not final until the sweep confirms nothing else
needs touching): app/(tabs)/search.tsx, src/api/search.ts,
src/hooks/useTrending.ts, src/utils/recommendationEventQueue.ts (if
exposure semantics need a new event type there), backend
app/services/query/search_query.py, app/services/search/search_engine.py,
app/services/search/search_ranker.py, app/api/v1/routes/search.py,
app/(tabs)/craves.tsx, app/profile-setup.tsx.
Verification plan: re-verify each of the 10 items above against current
code before touching (already done once above; re-check again
immediately before editing each file in case anything changed). Full
frontend suite + tsc --noEmit after frontend changes; backend test suite
after backend changes. New regression tests for: debounce-resurrection,
retry-actually-refetches, cuisine/category match, cancellation,
ranking-survives-pagination, craves failure->empty, profile-setup retry.

## Next action

Confirm each of the 10 items above is still accurate against this
branch's current search.tsx/craves.tsx/profile-setup.tsx/backend files,
then implement fixes one at a time, verifying after each.
