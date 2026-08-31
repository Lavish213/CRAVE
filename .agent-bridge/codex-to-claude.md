# H-20260831-scheduler-safe-rollout

Status: ready-for-review
Owner: Codex
Branch: `codex/scheduler-safe-rollout`
Base SHA: `924ce41`
Implementation commit: `1c3a773`
Locked files: see `.agent-bridge/STATE.md`

## Outcome

Railway production topology was verified directly: one CRAVE web service, no
cron, no standalone worker, and `RUN_EMBEDDED_SCHEDULER=false`. Creating the
existing worker service as-is would immediately register every backlog job.

This branch adds a standalone-worker-only, default-off rollout gate and an
explicit job allowlist. Disabled workers remain alive but create no scheduler.
Enabled workers refuse empty or unknown allowlists. `create_scheduler()` still
registers every job by default, preserving existing embedded/local behavior.
The phased deployment and kill switch are documented in
`docs/SCHEDULER_WORKER_ROLLOUT.md`.

## Verification

- Focused scheduler/recovery suite: `16 passed`.
- Full backend suite: `939 passed, 2 skipped, 33 warnings in 9.92s` with
  `TZ=UTC`.
- Production was not mutated; no scheduler service or job was enabled.

## Known gaps / risks

- Railway service provisioning remains intentionally unperformed until this
  safety change is independently reviewed, merged, and deployed.
- Menu/image/discovery/ranking jobs must stay off until their individual
  backlog caps and canary evidence exist.

## Next action

Review the PR diff and tests. If accepted, merge and confirm its Railway
deployment. Codex can then provision the standalone service with
`SCHEDULER_WORKER_ENABLED=false`; no job enablement is authorized by this PR.
