# Active agent state

Status: ready-for-review
Owner: Codex
Branch: codex/extraction-observability-pass
Base SHA: 3b9eb15d8d669711bf97575de6d03ee7c27f1ba2
Scope: Add deterministic menu replay fixtures, snapshot coverage/drift evidence,
successful-only JS endpoint recipe learning, and a bounded dry-run-first menu
population command on top of PR #53. Adversarial follow-up: make the corpus
fail on inflated false positives and add a navigation-only negative fixture.
Follow-up scope: live-validate remaining provider adapters, repair only verified
failures, then trace the image pipeline end to end and repair verified causes of
missing Feed images.
Locked files: `backend/app/services/menu/extraction/js/**`,
`backend/app/services/menu/extraction/replay_corpus.py`,
`backend/app/services/menu/extraction/snapshot_evidence.py`,
`backend/app/services/menu/extraction/jsonld_menu_extractor.py`,
`backend/app/services/images/image_matcher.py`,
`backend/app/services/images/image_ingest_service.py`,
`backend/app/services/images/image_reader.py`,
`backend/app/workers/image_worker.py`,
`backend/app/workers/image_processing_worker.py`,
`backend/app/services/menu/menu_extraction_router.py`,
`backend/app/pipeline/snapshot_writer.py`,
`backend/app/services/menu/menu_diagnostics.py`,
`backend/app/services/menu/menu_trigger.py`,
`backend/app/services/menu/processing/menu_orchestrator.py`,
`backend/app/services/menu/providers/provider_registry.py`,
`backend/app/services/menu/source_quality.py`,
`backend/app/services/workers/menu_worker.py`,
`backend/scripts/run_menu_extraction_corpus.py`,
`backend/scripts/populate_menus.py`,
`backend/tests/fixtures/menu_extraction/**`,
`backend/tests/test_menu_extraction_observability.py`,
`backend/tests/test_menu_population.py`,
`backend/tests/test_provider_registry_contract.py`,
`backend/tests/test_jsonld_menu_extractor.py`,
`backend/tests/test_image_matcher.py`,
`backend/tests/test_image_ingest_service.py`,
`backend/tests/test_image_reader.py`,
`backend/tests/test_image_worker_attempt_reset.py`,
`backend/tests/test_image_processing_worker.py`,
`backend/tests/test_image_worker_eager_load.py`,
`.agent-bridge/STATE.md`, `.agent-bridge/codex-to-claude.md`
Verification plan: Red-first targeted tests for recipe attribution, replay
fixtures, coverage metrics, and drift; then all extraction tests and full
backend pytest; finally run the corpus CLI in its sandbox fixture mode.
Next action: Claude reviews through commit `554c013` after PR #53, reruns the
recorded checks, and confirms the provider fixes plus the image matcher,
partial-gallery retry, failure-state reset, and free-source-first behavior.
Production discovery, extraction, and coverage probes were read-only; no live
population or image backfill execution has occurred.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
