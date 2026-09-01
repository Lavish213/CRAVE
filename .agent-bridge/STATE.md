# Active agent state

Status: ready-for-review
Owner: Codex
Branch: codex/scheduler-provisioning-handoff
Base SHA: 93bfeace87b3887185b48a292fb66a5084be154f
Scope: Record the completed, default-off production provisioning of the
standalone Railway `CRAVE-scheduler` service. No application code changed and
no scheduler job was enabled.
Locked files: `.agent-bridge/STATE.md`, `.agent-bridge/codex-to-claude.md`,
`CRAVE_STATUS.md`
Verification plan: Confirm the deployed SHA/start command, inspect runtime
logs, query production job-run records after worker start, and recheck the web
service health endpoint.
Verification result: Railway deployment
`3f151a42-eafe-46b1-9184-f46af7023cc2` succeeded at SHA `93bfeac`; logs contain
only `scheduler_worker_disabled no_jobs_will_run`; the production DB contains
zero job runs since worker start; web health is `status/db/cache/worker=ok`.
Known gaps: No job is enabled. The first allowlisted production job is a
separate gated phase. Railway Config as Code migration is future maintenance.
Next action: Claude independently reviews this bridge-only PR. After review,
request a separate authorization before enabling `moderation_queue_health_check`.

## Existing local work excluded from this bridge

The primary checkout's `eas.json`, `package.json`,
`frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` remain unrelated and untouched.
