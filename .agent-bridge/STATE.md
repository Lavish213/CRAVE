# Active agent state

Status: ready-for-review
Owner: Codex
Branch: codex/release-coordination
Base SHA: 51d515535e9736c11a2ff30c9deaef4661e169bb
Scope: Run the live Playwright release smoke suite, correct only confirmed
test-harness defects, and record production configuration evidence.
Locked files: `frontend/e2e/smoke.spec.ts`, `frontend/e2e/README.md`,
`.agent-bridge/STATE.md`, `.agent-bridge/codex-to-claude.md`
Verification plan: Run all three Playwright journeys against the configured
production API; record passes, honest credential-gated skips, and exact
external blockers.
Next action: Claude independently reviews the PR diff and verification; the
human supplies a dedicated seeded test account before the authenticated
journey can be claimed as passing.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
