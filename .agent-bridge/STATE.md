# Active agent state

Status: ready-for-review
Owner: Codex
Branch: chat/autonomous-pass-1
Base SHA: ea5c709ca049ba48a0f95a65911cf0d5e6bbb342
Scope: Finish PR #50 review by correcting the confirmed root/backend requirements mirror drift, then independently reverify the five-task implementation.
Locked files: requirements.txt, .agent-bridge/STATE.md, .agent-bridge/codex-to-claude.md
Verification plan: dependency mirror assertion and dry-run; full backend pytest; full frontend Jest and TypeScript; Playwright smoke where the required environment is available; CI, CodeQL, and CodeRabbit review.
Next action: Claude or the human independently inspects PR #50 and commit f4b305e; merge only after the pending CodeRabbit review completes or is explicitly deferred.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this bridge
was created. They are not owned by this task.
