# Active agent state

Status: ready-for-review
Owner: Codex
Branch: codex/free-pipeline-canaries
Base SHA: bb33cd0 (current main; PR #113 review record merged)
Scope: Record the explicitly-authorized, one-at-a-time production rollout of
free/local scheduler paths after queue measurement and bounded canaries.

Locked files: `docs/SCHEDULER_WORKER_ROLLOUT.md`, `CRAVE_STATUS.md`,
`.agent-bridge/STATE.md`, and `.agent-bridge/codex-to-claude.md`.

Production outcome: exact allowlist is
`moderation_queue_health_check,share_parser,image_processing_recovery,
video_processing`. Deployment `38b0556b-e1e9-4395-afea-3c128300b327`
started exactly four jobs at source SHA `bb33cd0`. Paid Google image ingestion,
bulk menu enrichment, discovery/population, score recompute, and ranking are
still disabled.

Verification: three bounded zero-queue canaries succeeded; natural share and
video schedules succeeded; R2 references resolve; Railpack installed ffmpeg
7.1.5; pip installed ai-edge-litert 2.2.0; production health remained fully
`ok`; worker CPU/memory stayed nominal. Exact evidence is in
`.agent-bridge/codex-to-claude.md`.

Known gap: no real video was queued, so real media transfer/encoding/inference
still needs a seeded device E2E pass. Empty input queues do not increase
catalog coverage. The next useful population path is a tiny reviewed website
menu canary—not another scheduler allowlist expansion.

Commit: `8cb3a02` (docs-only rollout evidence).

Next action: independently inspect commit `8cb3a02` and the production
evidence. Do not enable another job.

## Existing local work excluded from this bridge

The primary checkout's `eas.json`, `package.json`,
`frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` remain unrelated and untouched.
