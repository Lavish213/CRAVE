# H-20260828-live-e2e
Status: ready-for-review
Owner: Codex
Branch: codex/release-coordination
Base SHA: 51d515535e9736c11a2ff30c9deaef4661e169bb
Commit SHA: b4c347f
Allowed next files: none until review

## Outcome
Enabled the agreed balanced GitHub protection for `main`: six named required
checks, strict branch freshness, one approving review with stale approvals
dismissed, conversation resolution, no force pushes/deletions, and administrator
bypass retained. A live Playwright run then exposed missing production CORS for
the exact local E2E origin. Railway was configured with only
`http://127.0.0.1:4197`; the unchanged `main` deployment completed successfully
and its preflight now returns that exact origin. Feed and Search journeys reach
real production data and Place Detail. The harness now ignores off-screen
React Native Web duplicates when asserting the visible tier badge.

## Verification
- GitHub branch-protection GET -> six exact required contexts, strict=true,
  approvals=1, enforce_admins=false, force pushes/deletions disabled.
- Railway deployment `a6040b26-9f39-46a0-be7f-96d0e5d3e72c` -> SUCCESS at
  `51d515535e9736c11a2ff30c9deaef4661e169bb`.
- Exact-origin OPTIONS preflight -> HTTP 200 with
  `access-control-allow-origin: http://127.0.0.1:4197`.
- `cd frontend && npx tsc --noEmit -p .` -> clean.
- `cd frontend && npm test -- --runInBand` -> 299 passed, 31 suites; the
  process retained the repository's known open handle after reporting results.
- `cd frontend && PLAYWRIGHT_BROWSER_CHANNEL=chrome npm run test:e2e` ->
  2 passed, 1 skipped (11.5s).

## Known gaps / risks
- Save -> Craves -> Place Detail is not verified: no dedicated seeded account
  was available through `CRAVE_E2E_EMAIL` / `CRAVE_E2E_PASSWORD`.
- The public app API key remains exposed by design in client builds and was
  previously pasted in chat. Rotate it only as a coordinated client/backend
  release; changing Railway alone would break installed clients.
- No iOS Release build or physical-device smoke evidence yet.

## Next action
Review this diff and evidence. If correct, approve PR #51. Do not mark the
authenticated journey, iOS build, or device matrix complete.
