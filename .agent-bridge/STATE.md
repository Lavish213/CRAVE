# Active agent state

Status: ready-for-review
Owner: Codex
Branch: codex/population-readiness-pass
Base SHA: f8a7f751d9837314ab02eeed326348db7d32249e
Scope: Audit the canonical place/menu/image schema and free-source discovery
pipeline end to end, quantify production coverage read-only, and fix only
verified blockers that would corrupt or prevent a safe population run.
Locked files: `backend/app/db/models/place.py`,
`backend/app/services/discovery/promote_service_v2.py`,
`backend/tests/test_promotion_pipeline_v2.py`, `backend/alembic/versions/`,
`docs/`, `.agent-bridge/STATE.md`, `.agent-bridge/codex-to-claude.md`
Verification plan: Add regression tests for every confirmed identity/schema
defect; run targeted discovery tests, full backend tests, Alembic upgrade from
a fresh database, and read-only production coverage queries. Do not run any
production writes or bulk population job.
Next action: Claude/human independently reviews commit `4ece444`, the migration,
production-read-only evidence, and PR checks. Do not run a population write
until the PR is merged/deployed and the one-city canary gates in
`docs/POPULATION_READINESS.md` are accepted.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
