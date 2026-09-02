# H-20260902-screen-coverage-brief

Status: ready-for-review
Owner: Codex
Branch: codex/screen-journey-feed-detail-craves
Base SHA: e6b7d9b3d803fdf36154b4fe2cecc56a5d47d06b
Commit SHA: 89978f3
Allowed next files: docs/CLAUDE_EXECUTION_BRIEF_SCREEN_AND_COVERAGE_2026-09-02.md, .agent-bridge/STATE.md, .agent-bridge/claude-to-codex.md

## Outcome

Added an executable brief for two deliberately separate tracks: the Feed → Place Detail → Save/Craves UI journey and bounded free-source menu/photo coverage. It records the historical baseline, existing canary commands, safety gates, measurable outcomes, stop conditions, and PR boundaries.

## Verification

- `git diff --check` → passed with no output before commit.
- referenced-path existence loop covering every file/script named in the brief → passed with no `MISSING` output.
- baseline cross-check against `CRAVE_STATUS.md` and canary constraints against `docs/POPULATION_RELEASE_PASS_2026-09-01.md`/`docs/SCHEDULER_WORKER_ROLLOUT.md` → counts, allowlist, disabled jobs, and prior 0/3 menu + 1/2 hidden-image evidence match.

## Known gaps / risks

- Documentation only: no UI/backend code changed and no production job or canary ran.
- Production counts are explicitly labeled historical until reproduced.
- The branch name predates the user's pivot to a Claude brief; trust the declared diff scope, not the branch label.

## Next action

Review and merge this documentation-only change. Then claim exactly one track on a fresh Claude branch; keep UI work, extractor changes, production canaries, image promotion, and scheduler expansion in separate PRs.
