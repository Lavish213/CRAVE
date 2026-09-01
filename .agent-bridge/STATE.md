# Active agent state

Status: ready-for-review
Owner: Codex
Branch: codex/moderation-health-rollout
Base SHA: ff952c87227a9f0331696e0474017071c81e32b7
Scope: Enable exactly one bounded production scheduler job,
`moderation_queue_health_check`, verify the allowlist and runtime, and record
the evidence. No application code changed.
Locked files: `.agent-bridge/STATE.md`, `.agent-bridge/codex-to-claude.md`,
`CRAVE_STATUS.md`, `docs/SCHEDULER_WORKER_ROLLOUT.md`
Verification result: Railway deployment
`782d290e-a674-45cb-ab8d-e382b065e1d9` succeeded at SHA `ff952c8`; logs show
only `CRAVE moderation queue health check` added and
`scheduler_worker_started jobs=1`. A manual invocation of the identical job
function wrote a successful row at `2026-09-01 08:15:06 UTC` with
`summary=empty` and no error. Web health remained `status/db/cache/worker=ok`.
Known gaps: The first natural six-hour APScheduler fire has not occurred yet.
No allowlist expansion is authorized before that evidence is reviewed.
Next action: Claude independently reviews this bridge-only PR and later checks
the first natural job-run row. Keep every other scheduler job disabled.

## Existing local work excluded from this bridge

The primary checkout's unrelated dirty files remain untouched.
