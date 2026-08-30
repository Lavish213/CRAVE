# Active agent state

Status: ready-for-review
Owner: Codex
Branch: codex/overture-entity-review
Base SHA: 476ad3a7d85c46e48312a2e6f2265c22a1060782
Scope: Read the complete production batch `oakland-20260830-a`, independently
verify the current existence and identity of every staged candidate using
authoritative sources, and produce a release recommendation without unblocking,
resolving, promoting, deleting, or otherwise mutating production rows.
Locked files: .agent-bridge/STATE.md, .agent-bridge/codex-to-claude.md,
docs/POPULATION_CANARY_2026-08-30.md, and one new entity-review artifact.
Verification plan: export the exact batch read-only; reconcile each record by
name, address, website, and external ID; use current official sources first and
independent secondary evidence where needed; mark ambiguous, duplicate, moved,
or closed entities HOLD/REJECT; verify production batch counts remain unchanged.
Next action: Claude independently reviews commit `98d1ed7`, especially the
shared-domain branch fix and fixed-ID disposition manifest. Do not run the
production `--apply` command before merge and approval.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
