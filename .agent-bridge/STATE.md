# Active agent state

Status: handoff-pending
Owner: Claude
Branch: main
Base SHA: deb83b5 (PR #117 merged)
Scope: Root-caused and fixed both acquisition-pipeline failures from the
recent canary attempts (menu contamination on Itani, zero free image
candidates on two sites), rather than leaving them as open blockers.

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

Codex, when back, two independent things ready for you:
1. Retry the menu backlog canary (`run_menu_backlog_canary.py`) on Itani
   plus a small new batch from the website/no-menu candidates, now that
   the duplicate/entity gates are live -- watch for `reclaimed`/
   `materialized` counts and spot-check a few items for plausibility.
2. Retry the free-image-acquisition canary on the same two sites that
   returned zero candidates -- the browser-escalation fallback should
   now find their client-rendered photos; confirm via logs whether
   `website_image_browser_escalation_success` actually fires.

Plus the still-open image_processing_recovery synthetic test request
from before this pass (`.agent-bridge/claude-to-codex.md`) -- unrelated,
do in whichever order suits.

## Existing local work excluded from this bridge

The primary checkout's `eas.json`, `package.json`,
`frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` remain unrelated and untouched.
