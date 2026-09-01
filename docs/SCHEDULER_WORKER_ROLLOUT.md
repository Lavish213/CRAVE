# Standalone scheduler worker rollout

Date: 2026-08-31

## Verified production gap (original finding, 2026-08-31)

Railway had one `CRAVE` web service and Postgres. The web service had
`RUN_EMBEDDED_SCHEDULER=false`, no Railway cron was configured, and no separate
scheduler service existed. Consequently, no APScheduler job was running.

The standalone worker implementation already existed at
`app.scheduler_worker`. This change added the missing rollout brake; it did not
enable production jobs by itself.

## Current state (2026-09-01)

The gap above is now split into two independent facts — do not conflate them:

- **Service exists**: `CRAVE-scheduler` is provisioned on Railway, connected
  to `Lavish213/CRAVE` on `main`, deployed successfully (first deploy at SHA
  `93bfeac`).
- **No job runs**: `SCHEDULER_WORKER_ENABLED=false` and no
  `SCHEDULER_JOB_ALLOWLIST` are set on that service, so it stays alive and
  idle — confirmed via the deployed runtime log
  (`scheduler_worker_disabled no_jobs_will_run`) and a zero-row post-start
  production job-run check. Still zero APScheduler jobs running anywhere.
  Phase 1 below is done; phase 2 has not started.

## Required worker configuration

- Source: `Lavish213/CRAVE`, branch `main`
- Start command: `cd backend && python -m app.scheduler_worker`
- `SCHEDULER_WORKER_ENABLED=false` for initial provisioning
- `SCHEDULER_JOB_ALLOWLIST=` (empty) while disabled
- `DB_POOL_SIZE=2`
- `DB_MAX_OVERFLOW=2`
- The same required database, cache, storage, Supabase, monitoring, and
  provider variables as the web service, preferably through Railway reference
  variables rather than copied secret values

With the default-off switch, the process stays alive, handles SIGTERM, and
logs `scheduler_worker_disabled no_jobs_will_run`. It creates no scheduler and
runs no jobs.

## Phased release

1. **Done (2026-09-01).** Provisioned the service disabled. Verified the
   disabled log line and zero new job-run rows.
2. Set `SCHEDULER_WORKER_ENABLED=true` with
   `SCHEDULER_JOB_ALLOWLIST=moderation_queue_health_check`. This is one bounded
   `COUNT` query every six hours and proves scheduler execution without
   releasing an enrichment backlog.
3. Observe a completed `job_runs` row and nominal web health/error rate.
4. Add latency-sensitive recovery jobs one at a time only after their current
   queue depth is measured: `share_parser`, `video_processing`, then
   `image_processing_recovery`.
5. Keep `menu_enrichment`, `image_ingestion`, `discovery`, `osm_ingest`,
   `overture_ingest`, `score_recompute`, and `ranking_update` disabled until
   each backlog has its own reviewed batch cap and canary evidence.

## Kill switch and rollback

Set `SCHEDULER_WORKER_ENABLED=false` on the worker service and redeploy/restart.
The worker remains online but schedules nothing. Do not set
`RUN_EMBEDDED_SCHEDULER=true` on the web service as a fallback; that would move
CPU-heavy work back into the request process.

Rollback triggers include duplicate job-run rows, web error/latency regression,
unexpected paid-provider calls, database connection pressure, or any job
processing more records than its reviewed cap.

## A1 canary boundary

`scripts/run_menu_backlog_canary.py` is the only approved first-run path for
menu extraction. It requires exact reviewed place IDs, previews by default,
and requires an exact confirmation count. Enabling `menu_enrichment` in the
scheduler is not a substitute for that canary.
