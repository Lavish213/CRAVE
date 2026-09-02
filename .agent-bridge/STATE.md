# Active agent state

Status: ready-for-review
Owner: Claude
Branch: claude/place-issue-reporting (PR #128 open against main)
Base SHA: 6e32ba4 (main, post-PR#125 brief merge)
Commit SHA: 9fdc40d
Scope: New general place-issue reporting (wrong hours, closed,
duplicate, wrong menu) -- closes the "Report is photo-only" gap found
during the Place Detail action-completion audit, and directly serves
CRAVE_MASTER_EXECUTION_ROADMAP.md Phase 16's report requirement.
Independent of PR #126 (Track 1) and PR #127 (earlier audit sweep) --
all three currently open, none conflict.

Locked files: none -- handoff complete.

Verification: migration applied/rolled back/re-applied cleanly against
real Postgres 16 through the full chain; backend 1036/2 skipped (1025
baseline + 11 new); frontend tsc clean, 335/335 (331 baseline + 4 new).
Both new behavioral pieces (admin-gating, reason-value passthrough)
regression-checked individually.

Known gaps: no in-app admin UI for the review queue (matches the
existing image/video report pattern -- also API-only). Resolving a
report doesn't correct the underlying place data, only marks it
reviewed -- real data correction is separate, larger admin tooling.

Next action: review/merge PR #128. Independently, PRs #126 and #127
are also still open and unmerged -- all three are safe to merge in any
order (no file overlap between them).
