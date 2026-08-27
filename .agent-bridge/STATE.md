# Active agent state

Status: idle
Owner: human
Branch: main
Base SHA: 1632fc6
Scope: No active shared task. PR #50 (the five CHAT_TASK_BRIEF tasks) is
merged; the notification-tap-routing web regression it surfaced is fixed;
CRAVE_STATUS.md's test counts are corrected. See claude-to-codex.md for
the full handoff.
Locked files: none
Verification plan: Set when a task is claimed.
Next action: Claim one bounded task before an agent edits shared files.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
