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
verified, all 8 checks green). Independently verified two of CodeRabbit's
findings by reading the actual diffs rather than trusting either PR's
description, and posted the confirmed ones as PR comments (GitHub blocks a
formal APPROVE/REQUEST_CHANGES review on this account's own PRs, so review
verdicts are recorded as regular comments instead — see each PR thread).

## Verification
- PR #53: reproduced the bug by inspecting `ExtractedMenuItem`'s dataclass
  definition (`price_cents` only, `slots=True`, no `price` field) against
  seven remaining `ExtractedMenuItem(price=...)` construction sites in
  `jsonld_menu_extractor.py` (:157, :197) and all five `detect_*` functions
  in `pattern_detectors.py`. `menu_extraction_router.py`'s `_safe_extract()`
  catches the resulting `TypeError` at `logger.debug` and returns `[]`, so
  JSON-LD extraction and the entire pattern-detector fallback family
  silently return empty, unconditionally, on every call — the exact
  opposite of what this PR's title claims to fix. Full comment on the PR
  thread with exact line numbers and a one-line repro.
- PR #55: read `get_cursor_feed` in `backend/app/api/v1/routes/places.py` —
  the `has_location` and no-city branches cap candidates at `limit=100`
  before `rank_feed()` runs, so `min(len(candidates), 200)` collapses to
  100 regardless of `_MAX_FEED_SNAPSHOT_PLACES = 200`. Only the `city_id`
  branch actually requests 200. Not a crash, but a real under-delivery of
  the feature's own stated bound for the (likely most common) location-based
  path. Posted on the PR thread.
- PR #52: diff matched its description exactly (4 files, no scope creep),
  `UIBackgroundModes` fix matches the exact gap PR #51's native build
  surfaced, new config test correctly asserts it, all 8 required checks
  green. Merged as `141fe8b`.

## Known gaps / risks
- PR #54 (stacked on #53's branch) not yet independently diff-reviewed —
  blocked on #53's fix landing first since it inherits that branch's bug.
- PR #56 (population pipeline) and PR #57 (map clustering) not yet
  independently diff-reviewed by Claude. CodeRabbit flagged migration-
  rollback/concurrent-promotion concerns on #56 and hit its rate limit on
  #57 (no actual review produced there yet).
- `CRAVE_STATUS.md` still reflects pre-PR-#51 state in places; not updated
  this pass — deferred in favor of finishing the PR backlog read-through
  the user explicitly asked for first.

## Next action
Fix the two confirmed findings above (with regression tests that actually
exercise the previously-broken paths, since the existing suites didn't
catch either). Once #53 is fixed, Claude will re-review #53 and then #54.
Claude will separately do a first-pass diff review of #56 and #57.
