# H-20260901-free-pipeline-canaries

Status: ready-for-review
Owner: Codex
Branch: codex/free-pipeline-canaries
Base SHA: bb33cd0620442473766a8f8cf3b96f8b79512dcd
Commit SHA: 8cb3a02
Allowed next files: documentation/bridge review only

## Outcome

With explicit user authorization, expanded the production scheduler one job
at a time from the health check to three free/local paths: share parsing,
stale-image recovery, and video processing. Measured queues before every
mutation, ran separate bounded no-op canaries, fixed missing scheduler R2
configuration using Railway reference variables (never reading/copying secret
values), and installed ffmpeg through Railpack before admitting video.

Final exact allowlist:
`moderation_queue_health_check,share_parser,image_processing_recovery,
video_processing`. Paid Google image ingestion, bulk menu enrichment,
discovery/population, score recompute, and ranking remain disabled.

## Verification

- Production aggregate queue snapshot -> actionable shares=0, videos=0,
  stale image uploads=0; all 81,638 image rows were `ready`.
- Share canary -> job run `6bdbd816-950d-4a18-b8ed-b66b22a9c602`, success,
  `no_pending_items`, no error.
- Image-recovery canary -> job run
  `cf368fdf-a7bf-478c-a05c-686255d2b4bd`, success, `reclaimed=0`, no error.
- Video canary (with queue-drift assertion) -> job run
  `d5d5853b-28ca-47e4-84e2-d480c79eb744`, success, batch=0,
  approved/rejected/failed=0.
- Natural recurring share run -> job run
  `17b5193c-744a-41e0-997f-0d3679522bad`, success,
  `no_pending_items`.
- Natural recurring video run -> job run
  `3c0260b9-bdef-4631-a2c4-aca7e1d550f1`, success, batch=0,
  approved/rejected/failed=0, no error; started at
  `2026-09-01T19:50:21.060170Z` after the final deployment.
- Railway deployment `38b0556b-e1e9-4395-afea-3c128300b327` at source SHA
  `bb33cd0` -> SUCCESS; logs show exactly four added jobs, all other jobs
  removed, `scheduler_worker_started jobs=4`.
- Railpack build -> `ffmpeg 7.1.5` installed; pip build ->
  `ai-edge-litert 2.2.0` installed; sanitized environment checks -> all five
  R2 variables resolve on the scheduler through references.
- `curl -fsS https://crave-production.up.railway.app/health` ->
  `status=ok`, `db=ok`, `cache=ok`, `worker=ok`.
- Worker telemetry after rollout -> CPU current 0, observed max 0.0281;
  memory current 0.1263 GB, observed max 0.1540 GB.
- Production coverage snapshot -> 37,761 active places; menus 1,005 (2.66%);
  public images 15,313 (40.55%); primary images 13,802 (36.55%); websites
  14,133 (37.43%). Website/no-menu candidates=13,128;
  website/no-public-image candidates=7,816.
- `git diff --check` -> clean before commit `8cb3a02`.

## Known gaps / risks

- The video canary had no queued media, so it proves scheduling, database,
  configuration, and zero-queue behavior—not real R2 transfer, ffmpeg output,
  or classifier quality. A seeded real upload/device journey is still needed.
- The processors cannot fill an empty input queue. Large catalog gains require
  separate reviewed website-menu and free-image acquisition canaries.
- Menu enrichment and Google-backed image ingestion intentionally remain off.

## Next action

Independently inspect the docs-only diff and production evidence. Do not add
another recurring job. Next population work should select a tiny reviewed set
from the 13,128 website/no-menu candidates and use
`backend/scripts/run_menu_backlog_canary.py`; free image acquisition needs its
own source-specific canary before touching the 7,816 eligible places.
