# Active agent state

Status: claimed
Owner: Codex
Branch: codex/extraction-heuristics-pass
Base SHA: f8a7f751d9837314ab02eeed326348db7d32249e
Scope: Add an evidence-backed heuristic validation layer to the existing menu
extraction pipeline, with replay-focused tests, without replacing providers or
introducing paid services.
Locked files: `backend/app/services/menu/extraction/**`,
`backend/app/services/menu/providers/provider_normalizer.py`,
`backend/app/services/menu/providers/clover_extractor.py`,
`backend/app/services/menu/validation/**`,
`backend/app/services/menu/menu_extraction_router.py`,
`backend/app/pipeline/snapshot_writer.py`,
`backend/tests/test_menu_extraction_heuristics.py`,
`backend/tests/test_menu_extraction_router*.py`, `.agent-bridge/STATE.md`,
`.agent-bridge/codex-to-claude.md`
Verification plan: Prove each behavior red-first with targeted pytest; run all
menu/extraction tests; run the complete backend suite; inspect the final diff.
Next action: Audit the full extraction call graph and existing contracts before
writing the first failing test.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
