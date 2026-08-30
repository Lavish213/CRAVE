# Active agent state

Status: ready-for-review
Owner: Codex
Branch: codex/overture-production-apply-record
Base SHA: 5f4e81f075f9dc402905f095bdeca0f5be632343
Scope: Record the explicitly approved production application of reviewed batch
`oakland-20260830-a` and its independent database/API verification evidence.
Locked files: .agent-bridge/STATE.md, .agent-bridge/codex-to-claude.md,
docs/OVERTURE_ENTITY_REVIEW_2026-08-30.md.
Verification plan: independently query candidate/place states after commit;
check health and live Place Detail, Search, Map, Feed, and stale-ID visibility.
Next action: Claude independently checks the production state and reviews this
documentation-only record. No further population mutation is authorized by it.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
