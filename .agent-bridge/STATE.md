# Active agent state

Status: ready-for-review
Owner: Codex
Branch: codex/the-pass-gap-closure
Base SHA: d4bb22d
Commit SHA: 624e09f
Scope: Close verified integration gaps after The Pass without rebuilding
PRs #100-#106: accurate approved-video presence on secondary place surfaces,
and atomic ranking-to-existing-Hitlist visited synchronization.

Locked files: backend ranking/save/place response services and routes, focused
tests, `CRAVE_STATUS.md`, `.agent-bridge/STATE.md`, and
`.agent-bridge/codex-to-claude.md`.

Verification:
- focused backend suite: 61 passed
- full backend suite: 981 passed, 2 skipped
- `git diff --check`: clean

Known gaps: no production mutation, deployment, or device claim was made.
Frontend UI, scheduler configuration, and group compatibility were excluded.

Next action: Claude independently reviews commit `624e09f`, especially the
atomic transaction boundary and account/no-implicit-save tests, then reruns
the focused and full backend suites before merge.

Primary-checkout dirty files remain excluded and untouched: `eas.json`,
`package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md`.
