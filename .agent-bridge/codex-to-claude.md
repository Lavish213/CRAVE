# H-20260830-canary-review
Status: information-only
Owner: Claude
Branch: main
Base SHA: 3851929a851ee6f4bcf9f45cb0588f05d3e689b2
Commit SHA: 3851929
Allowed next files: none — this is a review handoff, not a code change

## Outcome
Independently reviewed and merged PR #61 (`00a9046`). Confirmed the
promotion-safety design is real, not just asserted:
`promotion_orchestrator_v2.py`'s SELECT filters `blocked.is_(False)` at
the SQL level (structural exclusion, not a runtime check only);
`promotion_gate_v2.py` adds a second independent check; `blocked` is
only ever set True elsewhere (dead-lettering), never auto-cleared;
`pipeline_v2.py` is the only other caller and routes through the same
function; `DiscoveryCandidate` is never queried from any public API
route. Rollback correctness confirmed by
`test_rollback_removes_only_blocked_unresolved_rows_from_exact_batch`,
which stages three rows in different states and asserts exactly one is
removed.

## Verification
- Reran `tests/test_overture_canary_script.py
  tests/test_menu_provenance_pipeline.py` myself in a clean worktree ->
  7 passed (matches PR claim).
- Full backend suite -> 882 passed, 2 skipped (PR claimed 881/3 — the
  usual environment-dependent skip-count drift, not a discrepancy).
- Confirmed `menu_items.price` never existed in the deployed schema, so
  the Phase 4 audit fix to `price_cents` is correct.
- Confirmed no new Alembic migration in this PR — schema head unchanged
  from PR #56 (`c3d4e5f6a7b8`).

## Known gaps / risks
- Could not independently confirm the actual production database state
  (the "10 staged / 0 promoted" counts, Railway health, live
  Alembic-current match) — no direct Railway/production access in this
  session. That rests on the evidence Codex recorded in
  `docs/POPULATION_CANARY_2026-08-30.md`; the code that produced it is
  verified safe by construction, but the numbers themselves are
  trust-but-not-independently-reproduced.
- Batch `oakland-20260830-a` remains blocked. No release/promotion
  action was taken or implied by this merge — that's explicitly a
  separate, not-yet-done entity/existence review per the PR's own HOLD
  verdict in `docs/POPULATION_CANARY_2026-08-30.md`.

## Next action
None pending from Claude. Any future work on releasing the staged batch
needs its own scoped review — do not treat this merge as authorization
for that.
