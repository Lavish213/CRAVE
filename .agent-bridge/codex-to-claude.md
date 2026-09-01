# H-20260901-scheduler-worker-provisioned-default-off

Status: ready-for-review
Owner: Codex
Branch: codex/scheduler-provisioning-handoff
Base SHA: 93bfeace87b3887185b48a292fb66a5084be154f
Commit SHA: pending
Allowed next files: `.agent-bridge/STATE.md`, `.agent-bridge/codex-to-claude.md`, `CRAVE_STATUS.md`

## Outcome

Provisioned the standalone Railway service `CRAVE-scheduler` in production,
connected it to `Lavish213/CRAVE` on `main`, and deployed commit
`93bfeace87b3887185b48a292fb66a5084be154f` with the explicit start command
`cd backend && python -m app.scheduler_worker`.

The service is fail-closed and currently runs zero jobs:

- `SCHEDULER_WORKER_ENABLED=false`
- `RUN_EMBEDDED_SCHEDULER=false`
- no `SCHEDULER_JOB_ALLOWLIST`
- no paid provider, storage, or Supabase signing credentials were granted

Only the minimum variables needed to boot safely were referenced from the
existing `CRAVE` service: `ADMIN_USER_IDS`, `APP_ENV`, `DATABASE_URL`, and
`SENTRY_DSN`. Database pool limits were set to 2 + 2 overflow.

## Verification

- Railway deployment `3f151a42-eafe-46b1-9184-f46af7023cc2` → `SUCCESS`,
  commit `93bfeace87b3887185b48a292fb66a5084be154f`.
- `railway logs --service 69b849d3-d255-4ab5-bb74-0b8fb94fea16 --latest --lines 100`
  → `scheduler_worker_disabled no_jobs_will_run`; no job-start or error line.
- Read-only production DB query after the worker started →
  `{'job_runs_since_worker_start': 0, 'jobs': []}`.
- `curl -fsS https://crave-production.up.railway.app/health` →
  `{"status":"ok","db":"ok","cache":"ok","worker":"ok"}`.

## Known gaps / risks

- No scheduler job has been enabled or exercised in production.
- Railway reports that root Config as Code is deprecated and continues to
  work only until 2026-12-01. The worker's start command was therefore set
  explicitly and verified in deployment metadata; migration to Railway IaC
  remains future infrastructure maintenance.
- The next phase can create production work and is not authorized by this
  handoff.

## Next action

Independently inspect this bridge-only diff and the Railway evidence. Do not
enable a job yet. The next separately gated phase is one explicit allowlisted
job, beginning with `moderation_queue_health_check` per
`docs/SCHEDULER_WORKER_ROLLOUT.md`.
