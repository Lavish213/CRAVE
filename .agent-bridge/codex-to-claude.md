# H-20260908-free-image-coverage

Status: ready-for-review
Owner: Codex
Branch: codex/free-source-coverage
Base SHA: 1d0339de555f3f733ebac70996b8b79c962f4b4e
Implementation commit: f63cd5a

## Outcome

Improved official-website image recall without adding paid calls or public promotion. The extractor now accepts valid short absolute URLs; reads Schema.org JSON-LD image/photo fields, Open Graph and Twitter aliases, image links/preloads, responsive picture sources, lazy-load attributes, and inline background images; chooses the strongest srcset candidate; and still excludes logos/icons and non-image resources.

Provider-claim expansion was investigated but deliberately not broadened: current menu item photos already feed the dedicated menu-image bridge, while generic recursive URL harvesting would create avoidable entity/asset contamination.

## Verification

- Focused image/canary suite: `25 passed`.
- Full backend suite: `1112 passed, 2 skipped`.
- Production canary: exact four active zero-image places; `32` free-source rows staged (`9 + 9 + 9 + 5`).
- Independent production DB recheck: `32 hidden`, `0 primary`, therefore `0 publicly visible`.
- No Google branch is reachable from the canary reader.

## Known gaps / risks

- All 32 candidates remain hidden and require human review before any promotion.
- The extractor can surface page presentation assets along with food/interior images; downstream scoring/review remains necessary.
- This task does not repair or retry the separate unfinished production `menu_enrichment` job row.

## Next action

Review PR and CodeRabbit findings. After merge, review the hidden canary gallery before promoting any image, then claim menu-enrichment reliability as a separate bounded task.

---

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
