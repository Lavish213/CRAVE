# Active agent state

Status: idle
Owner: Claude
Branch: main
Base SHA: 5e70a18 (PR #109 merged)
Scope: Reviewed and merged Codex's PR #109 (gap closure after The Pass:
accurate has_video on Decision Session/Recommendations/Saves/Trending/
saved-map, plus the ranking-to-existing-save visited hook). Verified the
transaction-atomicity and no-implicit-save claims directly at the code
level, not just from the PR summary, and closed two claims that were
true but untested.

## What I independently verified

- `_create_ranking()` calls `mark_existing_save_visited()` (flush-only)
  *before* the caller's `db.commit()` in both `start_ranking()` and
  `submit_comparison()` -- confirmed a rollback (the replay-tolerant
  `IntegrityError` path) reverts both writes together, and that a
  replayed submission can't double-process (the `IntegrityError` fires
  on the ranking's own flush, before the visited-marking call is ever
  reached).
- `has_video` wiring into decision_session.py/recommendations.py/
  saves.py/trending.py/saved_places_map_query.py all follow the exact
  pattern already proven safe in PR #102. `recommendations.py`/
  `trending.py` specifically have no dedicated test exercising
  `has_video` end-to-end -- flagged as low-risk (identical, already-
  tested pattern) rather than blocking.

## Two claims I found untested and closed myself (commit 616439e)

1. "Cannot affect discovery-intake rows" -- removing the `dedup_key`
   filter from `mark_existing_save_visited` (keeping only user_id/
   place_id) left the full 981-test suite green, meaning nothing
   actually proved this. Added
   `test_completed_ranking_does_not_mark_a_discovery_intake_row_visited`
   (a user with a discovery-intake HitlistSave row for the same place
   they later rank) -- verified it fails against the broken filter,
   restored, passes now.
2. "Preserves an existing visit timestamp" -- the
   `if save.visited_at is None:` guard had no dedicated test. Added
   `test_completed_ranking_preserves_an_earlier_visited_at` -- same
   revert/confirm-fails/restore cycle.

## Verification

Full backend suite on final integrated main: 983 passed, 2 skipped
(981 baseline + 2 new). `git diff --check` clean.

## Known gaps / risks

None from this pass that need Codex's attention -- PR #109 is merged
and green, both my additions are already part of it. Same standing gaps
as before: the `moderation_queue_health_check` production step, and the
minor recommendations.py/trending.py has_video test-coverage gap noted
above (not urgent).

## Next action

Nothing needed from Codex on this pass. Standing by for the next
production update or whatever's next.

## Existing local work excluded from this bridge

The primary checkout's `eas.json`, `package.json`,
`frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` remain unrelated and untouched.
