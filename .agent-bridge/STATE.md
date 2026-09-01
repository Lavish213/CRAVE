# Active agent state

Status: handoff-pending
Owner: Claude
Branch: main
Base SHA: e36af16 (PR #116 merged)
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

Since that gap was flagged, also merged PR #115 (mine, test-only): a new
local test proves `reclaim_stale_image_uploads()` and
`process_image_upload()` actually compose -- a genuinely stale row now
gets driven all the way to `status='failed'` through the real error
handling, not just selected. Regression-checked (removed the
`status='failed'` assignment, confirmed the new test fails, restored).
Full backend suite: 987 passed, 2 skipped (986 baseline + 1 new, exact
match). This proves the logic locally; it does not replace a real
production run, which still needs Codex's DB access.

Also merged PR #116 (mine, docs-only): `CRAVE_STATUS.md`'s "What's next"
production section and test count were stale relative to `main` --
still described only `moderation_queue_health_check` as enabled and
listed the other three jobs as a future step, when #114 already enabled
all four. Synced it, plus folded in the menu-canary contamination
finding, the free-image-acquisition low-recall finding, and this
queued synthetic test, so the doc no longer contradicts the agent-bridge
history it's meant to summarize.

Next action: see `.agent-bridge/claude-to-codex.md` for a precise,
ready-to-run synthetic production test of the same path (every real
production run of `image_processing_recovery` has hit an empty queue and
proven nothing beyond "the job executes") -- now backed by a passing
local proof of the exact logic it's testing. The menu-canary and
free-image-acquisition next-actions from the prior handoff still stand
and are unaffected -- do either in whichever order suits.

## Existing local work excluded from this bridge

The primary checkout's `eas.json`, `package.json`,
`frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` remain unrelated and untouched.
