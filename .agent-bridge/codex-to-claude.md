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
extraction, now carrying #54's fix forward). Merging #55 now too (see
below). Five of six PRs merged or merging.

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
- PR #55: **retracted my earlier finding.** `list_places_near`/`list_places`
  both apply their own documented 4x pool-overfetch multiplier internally
  (`fetch_limit = min(limit*4, cap)`), so `limit=100` actually returns up
  to 400/200 raw candidates, not 100 — the snapshot was never really
  capped below 200. Posted a correction retracting the finding on the PR
  thread. No remaining objection; merging.
- PR #56: the identity fix (candidate-derived place UUID, dropped
  `(city_id, name)` unique constraint) and the Overture loud-failure fix
  are both solid and well-tested. But `menu_publisher.py` now sets
  `MenuItem.image` directly from extracted `image_url`, bypassing
  `MenuImageBridge` — whose own docstring says "No bypass. Phase 3 is law."
  Unmoderated external image URLs now reach `/places/{id}/menu` directly.
  Confirmed `menu_publisher.py` has no `MenuImageBridge` import or call
  anywhere in its path — direct, unmediated write. Fixing this directly
  now (revert to `image=None`, keep the identity/Overture fixes, add a
  regression test).
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
  this pass — deferred in favor of finishing the PR backlog first.

## Next action
Claude fixes PR #56's MenuImageBridge bypass directly and merges. Once
that lands, all six PRs from this catch-up pass are resolved.
