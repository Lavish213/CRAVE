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
- **Four bounded free/local jobs are live**: `SCHEDULER_WORKER_ENABLED=true`
  with the exact allowlist `moderation_queue_health_check,share_parser,
  image_processing_recovery,video_processing`. Deployment
  `38b0556b-e1e9-4395-afea-3c128300b327` (source SHA `bb33cd0`) logged those
  four jobs added, every other job removed, and
  `scheduler_worker_started jobs=4`. The scheduler receives its five R2
  settings through Railway reference variables to the web service; values
  were never copied or printed. Railpack installs `ffmpeg 7.1.5`, the build
  installed `ai-edge-litert 2.2.0`, and the classifier model is present in
  the repository. Menu enrichment, Google image ingestion, discovery,
  OSM/Overture population, score recompute, and ranking remain disabled.

- **Canary evidence**: before expansion, production had zero actionable
  shares, videos, or stale image uploads. One-shots created successful
  `job_runs` rows for share parsing (`6bdbd816-950d-4a18-b8ed-b66b22a9c602`,
  `no_pending_items`), image recovery
  (`cf368fdf-a7bf-478c-a05c-686255d2b4bd`, `reclaimed=0`), and video
  processing (`d5d5853b-28ca-47e4-84e2-d480c79eb744`, batch size zero and
  no failures). The recurring share parser then fired naturally at
  `2026-09-01T19:44:45.694154Z` and succeeded. Recurring video processing
  fired naturally after the final deployment at
  `2026-09-01T19:50:21.060170Z` (job run
  `3c0260b9-bdef-4631-a2c4-aca7e1d550f1`) and completed successfully with an
  empty batch and no error. Post-rollout web health remained
  `status/db/cache/worker=ok`; worker CPU stayed nominal and memory remained
  below 0.16 GB during the observed window.

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
4. **Done (2026-09-01).** Measured zero actionable rows, ran separate bounded
   one-shots, and enabled `share_parser`, `image_processing_recovery`, then
   `video_processing`. Storage references, ffmpeg, and the ML runtime were
   fixed/verified before video was admitted to the allowlist.
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
