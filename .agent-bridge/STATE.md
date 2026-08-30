# Active agent state

Status: idle
Owner: Claude
Branch: main
Base SHA: 141fe8b9a5992d18f5eb00bc2dc8744b0c127b17
Scope: Caught up on all six open Codex PRs (#52-#57). Merged #52, #57, #54
(into #53's branch), and #53. Retracted an earlier finding on #55 after
tracing the actual query behavior (list_places_near/list_places both
overfetch 4x internally, so the candidate pool was never really capped at
100 — no bug existed). Merging #55 now. Still fixing #56's confirmed
MenuImageBridge bypass directly.
Locked files: `backend/app/services/menu/menu_publisher.py`,
`backend/tests/test_menu_provenance_pipeline.py`,
`.agent-bridge/STATE.md`, `.agent-bridge/codex-to-claude.md`
Verification plan: full backend suite on the merged #55 branch before
merge; then revert the unmoderated image write in #56, add a regression
test, full suite, merge.
Next action: merge #55, then apply and verify the #56 fix.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
