# H-20260901-moderation-health-forced-run

Status: ready-for-review
Owner: Codex
Branch: codex/moderation-health-forced-run-evidence
Base SHA: 99352ef
Commit SHA: pending
Allowed next files: documentation/bridge review only

## Outcome

At the user's explicit request, forced exactly one production execution of
`_job_moderation_queue_health_check()` using the scheduler service's current
production variables and the exact deployed `main` commit. No allowlist,
service configuration, deployment, paid-provider credential, or other job was
changed.

The job completed successfully and found the moderation queue empty. Updated
the canonical status and rollout docs, which still incorrectly said the
scheduler was default-off with zero jobs.

## Verification

- Railway production environment: Postgres, CRAVE, and CRAVE-scheduler all
  `SUCCESS`; scheduler deployment `141f26f5-d449-4f80-b32f-06d2108c5b9e`
  runs commit `99352ef`.
- Sanitized scheduler configuration: enabled=true, embedded=false, allowlist
  exactly `moderation_queue_health_check`, admin IDs configured.
- Production `job_runs` row `238fa4af-91ce-4ac7-8854-59bf8a5c580c` -> started
  `2026-09-01T14:32:09.952741Z`, finished
  `2026-09-01T14:32:11.132023Z`, success=true, summary=`empty`, error=false.
- `curl -fsS https://crave-production.up.railway.app/health` ->
  `status=ok`, `db=ok`, `cache=ok`, `worker=ok`.

## Known gaps / risks

- The normal six-hour recurring execution has not fired yet; the forced run
  proves the same job body and production database path, while the existing
  runtime logs independently prove APScheduler registered exactly that job.
- No next job is authorized by this handoff.

## Next action

Independently inspect this docs-only diff and the sanitized evidence. Keep the
current one-job allowlist unchanged. Before any next job, measure its queue,
freeze a cap/rollback trigger, and obtain separate authorization.
