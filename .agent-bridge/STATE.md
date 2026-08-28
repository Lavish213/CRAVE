# Active agent state

Status: handed-off
Owner: Codex
Branch: codex/release-coordination
Base SHA: 51d51555fd9e8ef3e53e5b724cd29788a1530749
Scope: Establish one evidence-driven release campaign, agree the Codex/Claude split, and start the first non-overlapping release-verification tracks.
Locked files: .agent-bridge/STATE.md, .agent-bridge/codex-to-claude.md
Verification plan: Claude independently reviews this handoff against CRAVE_STATUS.md and current main; each agent then records exact checks and artifacts for its own track before any source-code fix.
Next action: Claude reads codex-to-claude.md, corrects or acknowledges the plan, then claims the production-readiness audit on its own branch without touching Codex's E2E/native-verification files.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
