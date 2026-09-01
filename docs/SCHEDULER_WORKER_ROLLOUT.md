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
- **One bounded health job is live**: `SCHEDULER_WORKER_ENABLED=true` and
  `SCHEDULER_JOB_ALLOWLIST=moderation_queue_health_check`. Runtime logs from
  deployment `141f26f5-d449-4f80-b32f-06d2108c5b9e` show every other job
  removed and `scheduler_worker_started jobs=1`. An explicitly-authorized
  one-shot created `job_runs` row
  `238fa4af-91ce-4ac7-8854-59bf8a5c580c` (started
  `2026-09-01T14:32:09.952741Z`, finished
  `2026-09-01T14:32:11.132023Z`, success, summary `empty`, no error).
  Post-run `/health` remained `status/db/cache/worker=ok`. No enrichment,
  ingestion, recovery, score, or ranking job is enabled.

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
2. **Done (2026-09-01).** Set `SCHEDULER_WORKER_ENABLED=true` with
   `SCHEDULER_JOB_ALLOWLIST=moderation_queue_health_check`. This is one bounded
   `COUNT` query every six hours and proves scheduler execution without
   releasing an enrichment backlog.
3. **Done (2026-09-01).** Observed the successful one-shot `job_runs` row and
   nominal web health described above. The recurring six-hour schedule stays
   enabled for ongoing observation.
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
