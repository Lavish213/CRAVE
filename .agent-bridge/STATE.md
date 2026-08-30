# Active agent state

Status: in-progress
Owner: Claude
Branch: codex/population-readiness-pass
Base SHA: 141fe8b9a5992d18f5eb00bc2dc8744b0c127b17
Scope: Caught up on all six open Codex PRs (#52-#57). Merged #52, #57, #54
(into #53's branch), #53, and #55 (after retracting an earlier finding on
it — list_places_near/list_places both overfetch 4x internally, so the
candidate pool was never really capped at 100). Now fixing #56's confirmed
MenuImageBridge bypass directly: revert menu_publisher.py's unmoderated
`image=item.get("image_url")` write back to `image=None`, keeping this
PR's good identity and Overture fixes, plus a regression test.
Locked files: `backend/app/services/menu/menu_publisher.py`,
`backend/tests/test_menu_provenance_pipeline.py`,
`.agent-bridge/STATE.md`, `.agent-bridge/codex-to-claude.md`
Verification plan: full backend suite after the revert + new regression
test proving an extracted image_url never reaches MenuItem.image.
Next action: apply the fix, verify, merge to main.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
