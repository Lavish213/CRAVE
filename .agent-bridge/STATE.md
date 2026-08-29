# Active agent state

Status: ready-for-review
Owner: Codex
Branch: codex/extraction-observability-pass
Base SHA: 3b9eb15d8d669711bf97575de6d03ee7c27f1ba2
Scope: Add deterministic menu replay fixtures, snapshot coverage/drift evidence,
successful-only JS endpoint recipe learning, and a bounded dry-run-first menu
population command on top of PR #53.
Locked files: `backend/app/services/menu/extraction/js/**`,
`backend/app/services/menu/extraction/replay_corpus.py`,
`backend/app/services/menu/extraction/snapshot_evidence.py`,
`backend/app/services/menu/menu_extraction_router.py`,
`backend/app/pipeline/snapshot_writer.py`,
`backend/app/services/menu/menu_diagnostics.py`,
`backend/app/services/menu/menu_trigger.py`,
`backend/app/services/workers/menu_worker.py`,
`backend/scripts/run_menu_extraction_corpus.py`,
`backend/scripts/populate_menus.py`,
`backend/tests/fixtures/menu_extraction/**`,
`backend/tests/test_menu_extraction_observability.py`,
`backend/tests/test_menu_population.py`,
`.agent-bridge/STATE.md`, `.agent-bridge/codex-to-claude.md`
Verification plan: Red-first targeted tests for recipe attribution, replay
fixtures, coverage metrics, and drift; then all extraction tests and full
backend pytest; finally run the corpus CLI in its sandbox fixture mode.
Next action: Claude reviews commit `1684b20` after PR #53, reruns the recorded
checks, and confirms the population CLI remains preview-first. No live
population has been authorized or run.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
