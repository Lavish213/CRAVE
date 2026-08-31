# H-20260831-e2e-sweep

Status: information-only
Owner: Claude
Branch: main
Base SHA: 2d97f11
Allowed next files: none — this is a status handoff, not a code change

## Outcome
Codex, addressed to you directly, continuing from H-20260831-e5-e6-e7-
audit-pass. The user asked for an end-to-end sweep of the whole project
for gaps/bugs/anything broken -- fix what's fixable, log the rest for
you. Three merged since that handoff:

- **PR #82**: deleted 2 dead category-query files (0 importers anywhere,
  confirmed via repo-wide grep) -- an abandoned parallel implementation
  from the same commit that added the real, used category query files.
- **PR #83**: real IDOR fix. `GET /upload/status/{image_id}` required
  auth but never checked the image belonged to the caller -- any
  authenticated user could read another user's `moderation_reason`/
  `error_message`. Fixed to match `GET /videos/{video_id}`'s existing
  ownership check exactly. Found via a background research pass that
  also checked every other write/delete route in the app
  (blocks/follows/hitlist/rankings/saves/account/profile/moderation/
  menu_submissions) and confirmed they're all correctly scoped already
  -- this was the one real gap.
- **PR #84**: real N+1 fix. `menu_worker.py` called
  `recompute_places_v4(db, places=[place])` once per materialized place
  inside its per-place loop -- that function's own `_fetch_signal_context`
  is explicitly "batch-fetch ... never per-place", so this defeated its
  design (N places -> N x as many signal queries, N redundant per-city
  cache invalidations). Now batches once per worker batch instead.

## Verification
Full backend suite: 910 passed, 2 skipped (908 baseline + 2 new tests
across #83/#84). Both fixes independently verified to catch their own
regression (temporarily reverted, confirmed the new test failed,
restored) before merging -- same discipline as every prior fix this
session.

## Known gaps / risks
Also checked and confirmed NOT bugs, so don't re-investigate:
- `olo_extractor.py`'s "NOT IMPLEMENTED" -- genuine, correctly-documented
  (no public Olo API), not something to build around.
- `rate_limit.py`'s IP-vs-user keying -- already documented, already
  tracked in CRAVE_REMEDIATION_PLAN.md, not new.
- Repo-wide sweep for bare/silent excepts, SQL-injection-shaped string
  formatting, frontend timer/listener leaks: all clean.

Same production-access gaps as every prior handoff remain: A1 (backlog
run), A3 (2 dead menu sources), A7 (source discovery), B1 steps 2/4.

## Next action
Nothing from this sweep needs your follow-up -- both real findings are
already fixed and merged. When you're back: (1) A1 backlog run, (2) A3
with actual production row data, (3) B1 steps 2/4.
