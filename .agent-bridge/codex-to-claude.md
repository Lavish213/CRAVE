# H-20260830-pr-catchup
Status: information-only
Owner: Claude
Branch: main
Base SHA: 141fe8b9a5992d18f5eb00bc2dc8744b0c127b17
Commit SHA: 141fe8b
Allowed next files: none — this is a review/status handoff, not a code change

## Outcome
Read through all six open PRs (#52-#57) plus their CodeRabbit and bridge
comments after a session gap. Merged #52 (iOS UIBackgroundModes fix),
#57 (Map truth/clustering — independently reran its backend suite, no
concerns), #54 (extraction observability + population preview, merged
into PR #53's branch per its own base), and #53 itself (heuristic menu
extraction, now carrying #54's fix forward). Four of six PRs merged.
Independently verified findings on #53, #55, and #56 by reading the
actual diffs rather than trusting either PR's description, and posted
the confirmed ones as PR comments (GitHub blocks a formal
APPROVE/REQUEST_CHANGES review on this account's own PRs, so review
verdicts are recorded as regular comments instead — see each PR thread).

## Verification
- PR #53 (merged, now includes #54's fix): read the H-20260829-extraction-
  observability handoff above — Codex independently found and fixed the
  same `price=` constructor bug via a `coerce_price_cents()` normalizer,
  and added an AST-based static guard
  (`test_every_extracted_menu_item_constructor_uses_the_active_price_contract`)
  that fails if any `ExtractedMenuItem(...)` call anywhere in the menu
  service tree still passes `price=`. Confirmed via `git grep` zero
  remaining `price=` kwargs. Ran the full backend suite twice: 867 passed
  on #54's branch alone, then 869 passed, 2 skipped after merging latest
  `main` (#52/#57) into #53's branch — no interaction issues. Merged to
  `main` as `dfa026b`.
- PR #55: read `get_cursor_feed` in `backend/app/api/v1/routes/places.py` —
  the `has_location` and no-city branches cap candidates at `limit=100`
  before `rank_feed()` runs, so `min(len(candidates), 200)` collapses to
  100 regardless of `_MAX_FEED_SNAPSHOT_PLACES = 200`. Only the `city_id`
  branch actually requests 200. Not yet fixed.
- PR #56: the identity fix (candidate-derived place UUID, dropped
  `(city_id, name)` unique constraint) and the Overture loud-failure fix
  are both solid and well-tested. But `menu_publisher.py` now sets
  `MenuItem.image` directly from extracted `image_url`, bypassing
  `MenuImageBridge` — whose own docstring says "No bypass. Phase 3 is law."
  Unmoderated external image URLs now reach `/places/{id}/menu` directly.
  Not yet fixed.
- PR #52 and #57: both verified clean and merged. #57 confirmed by
  independently rerunning the focused Map tests (11 passed) and the full
  backend suite (820 passed, 2 skipped) in a clean worktree; all 8 required
  CI checks green on both.

## Known gaps / risks
- PR #53+#54's combined diff also includes a real, well-reasoned image-
  pipeline hardening pass (ImageMatcher Google resource-name support,
  ImageIngestService's complete-gallery threshold, ImageReader's free-
  source-first ordering, ImageWorker's block/attempt-count rehabilitation)
  that Codex's own bridge handoff documents in detail but the PR's GitHub
  description never mentioned. Noted on the PR thread as a disclosure gap,
  not a code-quality objection — the fixes themselves check out.
- `CRAVE_STATUS.md` still reflects pre-PR-#51 state in places; not updated
  this pass — deferred in favor of finishing the PR backlog read-through
  the user explicitly asked for first.

## Next action
Codex still needs to fix PR #55's 100-vs-200 candidate cap and PR #56's
MenuImageBridge bypass, each with a regression test that actually
exercises the previously-broken path. Claude re-reviews both once updated.
