# Active agent state

Status: ready-for-review
Owner: Codex
Branch: codex/production-population-canary
Base SHA: 8a9307d2be442b952b8885f04947827c31ed528a
Scope: Verify production health and migrations, capture a fresh read-only
population baseline, then prepare and execute at most one capped, reversible
single-city free-source canary if every preflight gate passes.
Locked files: .agent-bridge/STATE.md, .agent-bridge/codex-to-claude.md,
docs/POPULATION_READINESS.md, and any new canary audit artifact or narrowly
required canary script added on this branch.
Verification plan: inspect Railway health/config without exposing values; verify
Alembic head/current; run the existing backend test suite or the narrowest
production-safe checks; capture before/after counts, duplicates, rejection,
missing-field rates, runtime, and errors; stop before writes if rollback or
batch attribution is unavailable.
Next action: Claude independently reviews commit `00a9046`, the canary safety
controls, and the recorded production evidence before merge. Do not unblock
staged batch `oakland-20260830-a`.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
