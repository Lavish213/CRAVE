# Active agent state

Status: ready-for-review
Owner: Codex
Branch: codex/feed-keyset-pagination
Base SHA: f8a7f751d9837314ab02eeed326348db7d32249e
Scope: Replace the main Feed's shifting offset pagination with a bounded opaque
cursor snapshot while preserving the existing `/places` contract for other
callers.
Locked files: `backend/app/api/v1/routes/places.py`,
`backend/app/api/v1/schemas/places.py`,
`backend/app/services/feed/feed_cursor_snapshot.py`,
`backend/app/services/cache/cache_ttl.py`,
`backend/tests/test_feed_cursor_pagination.py`,
`frontend/src/api/places.ts`, `frontend/app/(tabs)/index.tsx`,
`frontend/__tests__/feed.test.tsx`,
`.agent-bridge/STATE.md`, `.agent-bridge/codex-to-claude.md`
Verification plan: Red-first backend insertion-between-pages regression and
cursor validation tests; red-first frontend cursor chaining test; then full
backend, frontend Jest, and TypeScript checks.
Next action: Claude independently reviews commit `a5cf587`, confirms the
legacy `/places` contract is unchanged, and reruns the focused cursor tests
before approving the pull request. Do not merge based on this handoff alone.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
