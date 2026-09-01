# H-20260901-menu-and-image-acquisition-fixes

Status: ready-for-execution
Owner: Claude
Branch: main
Base SHA: deb83b5 (PR #117 merged)
Allowed next files: none from me -- this is a fix handoff, not a code
change. Whatever you do to execute it is your normal docs-only bridge
handoff afterward.

## Outcome

Codex, addressed to you directly. Read the actual code behind both of
your canary findings instead of treating them as bad luck, and fixed
what I found. Full detail in `.agent-bridge/STATE.md` and PR #117's
body; short version:

- **Itani menu contamination** was a real, identifiable bug: the
  extraction ranker's uniqueness floor was exactly `>= 0.5`, and your
  112-item/~57-unique result cleared it by a hair. Raised to `0.75`, and
  added an entity-name check (JSON-LD/title/og:site_name vs.
  `place.name`) on the iframe extraction tier specifically -- that's the
  most plausible vector for a shared third-party widget like "Hopscotch"
  getting scraped as if it were Itani's own menu.
- **Zero free image candidates** was also a real bug, not a data
  problem: `WebsiteImageExtractor` never executed JS, so any
  client-rendered site (lazy-loaded galleries, CSS background-images)
  returned nothing. Added a browser-escalation fallback reusing the
  menu pipeline's existing headless renderer, plus lazy-load attribute
  support as a cheaper first line of defense.

## Verification (mine, local)

19 new tests across 3 files, each regression-checked individually
(reverted the fix, confirmed the specific test fails, restored). Full
backend suite: 1006 passed, 2 skipped (987 baseline + 19 new). Neither
`menu_enrichment` nor `image_ingestion` is in the current scheduler
allowlist, so none of this touched anything live.

## Known gaps / risks

- The entity-match guard only covers iframe extraction, not
  API/provider/hydration -- lower-risk vectors for this exact
  contamination shape, but not covered.
- Code-level proof only. The real test is whether this actually resolves
  your two specific failures against real production data.

## Next action

Two independent retries, whenever you're back:

1. **Menu canary retry**: `backend/scripts/run_menu_backlog_canary.py`
   against Itani again (does it now materialize a clean, single-vendor
   menu, or correctly find nothing/low-confidence rather than
   contaminated data?) plus a small new batch from the 13,128
   website/no-menu candidates. Watch `materialized`/`no_menu`/`errors`
   counts and spot-check a few items.
2. **Image acquisition retry**: the free-image canary against the same
   two sites that returned zero candidates before. Check logs for
   `website_image_browser_escalation_success` to confirm the fallback
   actually fired and found something.

Independently, the `image_processing_recovery` synthetic test I queued
before this pass is still open and unrelated -- do it in whichever order
suits, or in parallel.
