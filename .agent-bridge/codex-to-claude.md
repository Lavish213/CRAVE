# H-20260830-pr-catchup
Status: information-only
Owner: Claude
Branch: main
Base SHA: 141fe8b9a5992d18f5eb00bc2dc8744b0c127b17
Commit SHA: 141fe8b
Allowed next files: none — this is a review/status handoff, not a code change

## Outcome
Read through all six open PRs (#52-#57) plus their CodeRabbit and bridge
comments after a session gap. Merged #52 (iOS UIBackgroundModes fix — clean,
verified, all 8 checks green) and #57 (Map truth/clustering — independently
reran its backend suite, no concerns). Independently verified findings on
#53, #55, and #56 by reading the actual diffs rather than trusting either
PR's description, and posted the confirmed ones as PR comments (GitHub
blocks a formal APPROVE/REQUEST_CHANGES review on this account's own PRs,
so review verdicts are recorded as regular comments instead — see each PR
thread).

## Verification
- PR #53: reproduced the bug by inspecting `ExtractedMenuItem`'s dataclass
  definition (`price_cents` only, `slots=True`, no `price` field) against
  seven remaining `ExtractedMenuItem(price=...)` construction sites in
  `jsonld_menu_extractor.py` (:157, :197) and all five `detect_*` functions
  in `pattern_detectors.py`. `menu_extraction_router.py`'s `_safe_extract()`
  catches the resulting `TypeError` at `logger.debug` and returns `[]`, so
  JSON-LD extraction and the entire pattern-detector fallback family
  silently return empty, unconditionally, on every call — the exact
  opposite of what this PR's title claims to fix.
- PR #55: read `get_cursor_feed` in `backend/app/api/v1/routes/places.py` —
  the `has_location` and no-city branches cap candidates at `limit=100`
  before `rank_feed()` runs, so `min(len(candidates), 200)` collapses to
  100 regardless of `_MAX_FEED_SNAPSHOT_PLACES = 200`. Only the `city_id`
  branch actually requests 200.
- PR #56: the identity fix (candidate-derived place UUID, dropped
  `(city_id, name)` unique constraint) and the Overture loud-failure fix
  are both solid and well-tested. But `menu_publisher.py` now sets
  `MenuItem.image` directly from extracted `image_url`, bypassing
  `MenuImageBridge` — whose own docstring says "No bypass. Phase 3 is law."
  Unmoderated external image URLs now reach `/places/{id}/menu` directly.
- PR #52 and #57: both verified clean and merged. #57 confirmed by
  independently rerunning the focused Map tests (11 passed) and the full
  backend suite (820 passed, 2 skipped) in a clean worktree; all 8 required
  CI checks green on both.

## Known gaps / risks
- PR #54 (stacked on #53's branch) not yet independently diff-reviewed —
  blocked on #53's fix landing first since it inherits that branch's bug.
- `CRAVE_STATUS.md` still reflects pre-PR-#51 state in places; not updated
  this pass — deferred in favor of finishing the PR backlog read-through
  the user explicitly asked for first.

## Next action
Fix the three confirmed findings above (PR #53, #55, #56), each with a
regression test that actually exercises the previously-broken path, since
the existing suites didn't catch any of them. Once #53 is fixed, Claude
will re-review #53 and then #54.
