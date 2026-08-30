# H-20260830-production-population-canary
Status: ready-for-review
Owner: Codex
Branch: codex/production-population-canary
Base SHA: 8a9307d2be442b952b8885f04947827c31ed528a
Commit SHA: 00a9046
Allowed next files: review only; do not release or edit production canary rows

## Outcome
Added a preview-first, capped Overture population canary with explicit staging
and exact-batch rollback. Staged production batch `oakland-20260830-a` contains
exactly 10 candidates; every row remains blocked, unresolved, and unpromoted.
Also repaired the Phase 4 audit's stale menu-price column and added a narrow
publisher guard against obvious zero-signal test menu items.

## Verification
- Full backend: 881 passed, 3 skipped.
- Focused canary/provenance tests: 7 passed.
- Python compilation and `git diff --check`: clean.
- Production health: API, database, cache, and worker all healthy.
- Production Alembic current and code head: `c3d4e5f6a7b8`.
- Oakland preview: 769 fetched, 10 selected; all had address/category, eight
  had websites, and five were flagged as likely duplicates.
- Staged batch: 10 rows, 10 blocked, 0 resolved, 0 promoted.
- Legacy-image scoring dry-run: 2,530 inspected; 2 candidate-primary, 2,418
  gallery-only, 110 hidden. No write was executed because the signal was weak.

## Known gaps / risks
- Do not unblock or promote this batch. Overture contains stale aliases and at
  least one moved venue in the reviewed sample.
- Two existing placeholder menu rows remain until the guard is deployed and
  their source menus are republished or cleaned through a separately reviewed
  operation.
- Provider-menu coverage remains zero until existing menus are rematerialized.
- The legacy-image backfill was intentionally held because 90.3% of rows still
  had unknown content classification.

## Next action
Claude independently inspects commit `00a9046`, the canary script's stage and
rollback constraints, the tests, and `docs/POPULATION_CANARY_2026-08-30.md`.
Approve or request changes on the PR. Keep `oakland-20260830-a` blocked pending
a separate existence/entity review and release decision.
