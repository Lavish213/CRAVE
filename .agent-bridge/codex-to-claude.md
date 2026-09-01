# H-20260901-moderation-health-single-job-rollout

Status: ready-for-review
Owner: Codex
Branch: codex/moderation-health-rollout
Base SHA: ff952c87227a9f0331696e0474017071c81e32b7
Commit SHA: pending
Allowed next files: `.agent-bridge/STATE.md`, `.agent-bridge/codex-to-claude.md`, `CRAVE_STATUS.md`, `docs/SCHEDULER_WORKER_ROLLOUT.md`

## Outcome

Enabled the standalone production scheduler with exactly one allowlisted job:

- `SCHEDULER_WORKER_ENABLED=true`
- `SCHEDULER_JOB_ALLOWLIST=moderation_queue_health_check`

No other variable, credential, job, service, or application file changed.
Deployment `782d290e-a674-45cb-ab8d-e382b065e1d9` succeeded at application SHA
`ff952c87227a9f0331696e0474017071c81e32b7`.

## Verification

- Pre-enable production baseline → zero pending-review images; the three most
  recent historical health-check rows were successful with `summary=empty`.
- Deployment logs → only `CRAVE moderation queue health check` was added;
  every other scheduler job was removed; `scheduler_worker_started jobs=1`.
- Bounded manual invocation of the identical job function → completed.
- Latest production `job_runs` row → started
  `2026-09-01 08:15:06.492950+00:00`, finished
  `2026-09-01 08:15:09.230396+00:00`, `success=True`, `summary=empty`,
  `error=None`.
- Post-enable web health → `{"status":"ok","db":"ok","cache":"ok","worker":"ok"}`.

## Known gaps / risks

- APScheduler's interval starts six hours after worker startup. The manual run
  proves the bounded function and observability path, but the first natural
  scheduler fire remains pending around 14:11 UTC.
- Do not expand the allowlist until that natural run is observed and reviewed.
- Kill switch remains `SCHEDULER_WORKER_ENABLED=false` followed by redeploy.

## Next action

Review this documentation-only diff and the evidence above. Later verify a new
natural `moderation_queue_health_check` row after the six-hour interval. Keep
all other jobs disabled; no allowlist expansion is authorized by this handoff.
