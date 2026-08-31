# Active agent state

Status: ready-for-review
Owner: Codex
Branch: codex/autonomous-remainder-pass
Base SHA: ba261a5f
Scope: Autonomous data-readiness pass: production evidence for classifier,
menus, images, and ranking; repair operational reporting; add a simulation-first
maintenance path for unmistakable placeholder menu rows. No production writes.
Locked files: .agent-bridge/STATE.md, .agent-bridge/codex-to-claude.md,
docs/FOOD_CLASSIFIER_PRODUCTION_STATUS_2026-08-30.md,
docs/DATA_READINESS_AUDIT_2026-08-30.md,
backend/scripts/menu_coverage_report.py,
backend/scripts/deactivate_placeholder_menu_items.py, and focused tests for
those scripts.
Verification plan: read-only Railway SQL aggregates; focused backend tests;
full backend suite; script dry-run against production; git diff check. Production
mutation is explicitly excluded.
Next action: Claude reviews PR #68, reruns the full backend suite, and validates
the source-success semantics, guarded cleanup, and separate Railway scheduler
evidence. No scheduler config change or production apply is authorized by this
handoff. If accepted, the next operational investigation is bounded menu-job
throughput/yield, not re-enabling the embedded scheduler.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
