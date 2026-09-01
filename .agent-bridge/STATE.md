# Active agent state

Status: implementing
Owner: Codex
Branch: codex/moderation-health-forced-run-evidence
Base SHA: 99352ef (PR #112 merged)
Scope: Record the explicitly-authorized production one-shot of only
`moderation_queue_health_check` and correct stale scheduler rollout/status
documentation. No other job or variable change is in scope.

Locked files: `CRAVE_STATUS.md`, `docs/SCHEDULER_WORKER_ROLLOUT.md`,
`.agent-bridge/STATE.md`, and `.agent-bridge/codex-to-claude.md`.

Verification: production `job_runs` row
`238fa4af-91ce-4ac7-8854-59bf8a5c580c` succeeded with summary `empty` and no
error; production `/health` returned status/db/cache/worker all `ok`; Railway
reports Postgres, CRAVE, and CRAVE-scheduler `SUCCESS`.

Next action: commit this evidence-only documentation update and request
independent review. Do not enable another job without a separate queue-depth,
cap, rollback, and authorization gate.

Primary-checkout dirty files remain excluded and untouched.
