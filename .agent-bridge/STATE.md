# Active agent state

Status: handoff-pending
Owner: Claude
Branch: main
Base SHA: da74a7c (PR #114 merged)
Scope: Independently reviewed Codex's PR #114 (free-pipeline canaries:
share_parser, image_processing_recovery, video_processing admitted to the
production scheduler allowlist alongside moderation_queue_health_check) and
merged it.

Verification performed by Claude before merging: confirmed the diff touched
exactly the 4 claimed docs/bridge files with no application or
scheduler-config code; confirmed the final allowlist, deployment ID
(`38b0556b-e1e9-4395-afea-3c128300b327` at source SHA `bb33cd0`), and all six
job-run IDs (3 bounded canaries + 2 natural recurring runs) are stated
identically everywhere they appear; independently recomputed the coverage
percentages (menus 2.66%, public images 40.55%, primary images 36.55%,
websites 37.43% of 37,761 active places) and they match; confirmed paid
Google image ingestion, bulk menu enrichment, discovery/population, score
recompute, and ranking remain explicitly disabled (matches the user's
"free ways only" instruction, no scope creep); confirmed no secrets/
credentials/raw user data in the diff. Full write-up posted as a PR comment
on #114. Same limitation as the #113 review: this session has no Railway/
production access, so the underlying infra evidence itself is taken on
trust -- only repo-checkable claims were independently verified.

Known gap (carried forward from #114): no real video was queued during the
canary, so real R2 transfer/ffmpeg encoding/classifier quality is still
unverified -- needs a seeded device E2E pass, not another allowlist change.
Empty input queues also mean these four jobs alone won't grow catalog
coverage (menus 2.66%, images 40.55%) -- the next useful population step is
a tiny reviewed website-menu canary via the existing, already-reviewed
`backend/scripts/run_menu_backlog_canary.py` (13,128 website/no-menu
candidates available), not another scheduler job.

Next action: superseded by the new handoff below -- see
`.agent-bridge/claude-to-codex.md` for a precise, ready-to-run synthetic test
of `image_processing_recovery`'s actual reclaim behavior (every real run so
far has hit an empty queue and proven nothing beyond "the job executes").
The menu-canary and free-image-acquisition next-actions from the prior
handoff still stand and are unaffected -- do either in whichever order suits.

## Existing local work excluded from this bridge

The primary checkout's `eas.json`, `package.json`,
`frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` remain unrelated and untouched.
