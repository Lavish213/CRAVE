# Active agent state

Status: handoff-pending
Owner: Claude
Branch: main
Base SHA: 56b7cef (PR #121 merged + doc sync)
Scope: Root-caused and fixed both acquisition-pipeline failures from the
recent canary attempts (menu contamination on Itani, zero free image
candidates on two sites), rather than leaving them as open blockers.
Also triaged the ~26 open dependabot PRs (PRs #119, #120), and closed
the "real ffmpeg+classifier quality unverified" gap (PR #121).

## PR #121 (merged) -- real video pipeline, proven for real

The user asked whether the video food-classifier pipeline could be
tested or patched. ffmpeg wasn't installed in this session -- installed
it (apt, no application-code implication), then built real short videos
from the existing real food/non-food test fixture images and ran them
through the actual production functions (`check_duration_ms`,
`compress_video`, `score_video` -- real ffmpeg frame extraction into the
real TFLite model, nothing mocked). Food video scored 0.972, non-food
scored 0.402, threshold is 0.8 -- both correct. Wrote this as a
permanent, CI-skip-safe test (skips cleanly where ffmpeg is absent,
same pattern as the existing TFLite-runtime skip). Regression-checked.
Full backend suite: 1016 passed, 2 skipped (1014 baseline + 2 new).

This closes the ffmpeg+classifier half of the flagged gap. What's still
open: a real device-recorded video through the actual R2/scheduler path
in production -- server logic is now proven, camera capture and R2
transfer are not, and neither is testable without a physical device /
production access.

## Dependabot triage (PRs #119, #120)

Merged 5 GitHub Actions bumps directly (zero runtime risk), then
applied 8 backend + 3 frontend dependency bumps as two combined
commits (several touched adjacent lines in the same file, so
merging dependabot's PRs one at a time via GitHub kept hitting
conflicts) -- verified against the actually-installed upgraded
packages, not just edited version ranges: full backend suite 1014
passed unchanged, full frontend jest suite 331 passed unchanged,
`tsc --noEmit` clean. Closed the now-redundant dependabot PRs.

Closed PR #5 (starlette) without applying -- `requirements.txt`
already carries a deliberate uncapped `>=1.3.1` (see its own comment)
that PR #5 would have re-capped at `<2.0.0`, undoing a considered
prior decision.

Left 5 PRs open, each with a comment explaining why: #25 (react-dom)
and #27 (jest-expo) peer-require a newer `react` than the pinned
`19.1.0` -- real peer-dependency mismatches, not just version-range
nits, and #27 is also version-aligned to a newer Expo SDK than this
app's current `~54.0.33`. #28 (expo-location), #23
(react-native-worklets), #18 (react-native-maps), #8 (async-storage)
are native modules needing real device/simulator validation this
session doesn't have. #20 (react itself) should move together with
#25/#27 as one coordinated upgrade, not piecemeal. PR #49 (unrelated
feature, not a dependency bump) untouched.

## PR #117 (merged) -- what changed and why

**Menu contamination:** the Itani canary materialized 112 items with
only ~57 distinct names (~0.5 unique ratio) -- traced to
`extraction_result_ranker.py`'s `is_plausible_extraction_result()`
uniqueness floor being exactly `>= 0.5`, so a two-vendor merge cleared it
by a hair. Raised to `0.75`. Separately, nothing anywhere in the pipeline
verified scraped content actually declared itself as the target place --
added `app/services/menu/extraction/entity_match.py` (JSON-LD Restaurant/
LocalBusiness name, `<title>`, `og:site_name`, fuzzy-matched against
`place.name`) and wired it into the router's iframe extraction tier
specifically (the most plausible vector for a shared third-party
ordering widget like the "Hopscotch" contamination).

**Image acquisition:** `WebsiteImageExtractor` only ever did a plain
`requests.get()` + static BeautifulSoup parse -- zero JS execution, so a
site that renders photos client-side (lazy-loaded galleries, CSS
background-images) yields nothing. Added a browser-escalation fallback
reusing the menu pipeline's existing headless Playwright renderer
(`browser_escalation.py`'s `fetch_with_browser`), plus lazy-load
attribute support (`data-src`/`srcset`) as a cheaper first line of
defense.

Verification: 19 new tests (3 files), each regression-checked
individually (reverted the specific fix, confirmed its test fails,
restored). Full backend suite: 1006 passed, 2 skipped (987 baseline + 19
new, exact match). Neither `menu_enrichment` nor `image_ingestion` is in
the current production scheduler allowlist, so this carried no live
blast radius.

## PR #118 (merged) -- following up after the user asked to triple-check

Before extending #117's fix into `ExtractionController`, verified the
actual call graph first: `MasterDataOrchestrator.ensure_place()` routes
any non-Grubhub place (the majority) through `ExtractionController` +
`MenuOrchestrator.run_with_items()`, which shares zero code with
`menu_extraction_router.py` -- #117 never touched this path. Confirmed
via GitHub (PR #61, merged 2 days before this session) that this
"Phase 4" system is actively maintained, not legacy, and via
`docs/PHASE_PLAN.md`/`docs/MENU_INGEST_SYSTEM.md` that
`scripts/run_phase4_batch.py` is the officially documented tool for this
exact work.

Instead of duplicating #117's checks into `ExtractionController`, found
the better fix: `menu_pipeline.py`'s `process_extracted_menu()` is the
ONE quality gate both `run_for_place()` and `run_with_items()` call
before emitting claims. Added the same duplicate-name-ratio check there
-- covers every menu-writing path including `ExtractionController`'s,
from one place. Separately, `run_phase4_batch.py` had zero confirmation
gate (no preview, no `--run`, `--limit` optional/unbounded) -- added
`--run` (default preview-only) and a required, capped `--limit` (200),
matching `run_menu_backlog_canary.py`'s discipline. Updated both stale
docs' example commands to match.

Verification: 8 new tests, each regression-checked individually. Full
backend suite: 1014 passed, 2 skipped (1006 baseline + 8 new, exact
match).

Known gap: entity-match (JSON-LD/title vs. place name) still isn't wired
into `ExtractionController`'s path -- it doesn't retain fetched HTML in
its result, so that would need a moderate plumbing change. The
duplicate-ratio gate is the more broadly-protective fix and covers the
confirmed incident's shape regardless.

## Prior passes this session (summarized -- full detail in PR bodies)

Reviewed and merged Codex's PR #113 (moderation-health forced-run
evidence) and #114 (free-pipeline canaries -- share_parser,
image_processing_recovery, video_processing added to the allowlist).
Merged my own PR #115 (local proof that image-recovery reclaim logic
actually terminates a stale row, not just selects it) and #116 (synced
`CRAVE_STATUS.md`, which had gone stale relative to #114).

## Known gaps / risks

- The entity-match guard only covers the iframe tier, not API/provider/
  hydration extraction -- lower-risk vectors for this specific
  contamination shape, but a future incident there wouldn't be caught.
- This is code-level proof. It still needs a real production retry to
  confirm it actually resolves the two specific failures.
- The image-recovery synthetic test spec from the prior handoff (see
  `.agent-bridge/claude-to-codex.md`) is still open and unrelated to this
  PR -- both can proceed independently.

## Next action

Codex, when back, three independent things ready for you:
1. Retry the menu backlog canary (`run_menu_backlog_canary.py`) on Itani
   plus a small new batch from the website/no-menu candidates, now that
   the duplicate/entity gates are live -- watch for `reclaimed`/
   `materialized` counts and spot-check a few items for plausibility.
2. Retry the free-image-acquisition canary on the same two sites that
   returned zero candidates -- the browser-escalation fallback should
   now find their client-rendered photos; confirm via logs whether
   `website_image_browser_escalation_success` actually fires.
3. If/when `scripts/run_phase4_batch.py` is ever run (per
   `docs/PHASE_PLAN.md`'s Phase 4 plan), it now requires `--limit` (max
   200) and `--run` to execute -- preview first, review the sample, then
   `--run`. This path's quality gate is now protected by #118, but still
   weaker than the router's, so keep batches small.

Plus the still-open image_processing_recovery synthetic test request
from before this pass (`.agent-bridge/claude-to-codex.md`) -- unrelated,
do in whichever order suits.

## Existing local work excluded from this bridge

The primary checkout's `eas.json`, `package.json`,
`frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` remain unrelated and untouched.
