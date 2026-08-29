# Active agent state

Status: ready-for-review
Owner: Codex
Branch: codex/notification-release-fix
Base SHA: f8a7f751d9837314ab02eeed326348db7d32249e
Scope: Fix the confirmed iOS notification background-mode configuration,
verify generated native metadata, and classify the expo-notifications
persisted-registration warning against the installed SDK and upstream fix.
Locked files: `frontend/app.json`, notification configuration tests if needed,
`.agent-bridge/STATE.md`, `.agent-bridge/codex-to-claude.md`
Verification plan: Validate Expo config, run prebuild in a disposable copy,
assert generated Info.plist modes, then run frontend typecheck/tests.
Next action: Claude independently reviews commit `30a801e`, generated native
metadata evidence, and the upstream-warning classification before merge.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
