# Active agent state

Status: ready-for-review
Owner: Codex
Branch: codex/autonomous-remainder-pass
Base SHA: ba261a5f
Scope: Read-only verification of whether the real food-content classifier is
installed and executing in production or whether image classification silently
falls back to heuristics.
Locked files: .agent-bridge/STATE.md, .agent-bridge/codex-to-claude.md, one new
dated investigation artifact under docs/.
Verification plan: trace model selection and fallback code; inspect Railway
service variables/deployment/runtime evidence without printing secrets; compare
production classification distributions and recent records; make no mutation.
Next action: Claude independently inspects the report and the referenced code;
the live classifier proof remains part of the controlled device upload pass.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
