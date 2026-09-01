# H-20260901-menu-pipeline-fixes-complete

Status: ready-for-execution
Owner: Claude
Branch: main
Base SHA: 76513cf (PR #118 merged)
Allowed next files: none from me -- this is a fix handoff, not a code
change. Whatever you do to execute it is your normal docs-only bridge
handoff afterward.

## Outcome

Codex, addressed to you directly. Two PRs closing out the menu/image
acquisition contamination and recall bugs, including one you'd want to
know about even if you never touch it: `run_phase4_batch.py` had zero
confirmation gate before this.

**PR #117:** fixed the two things you found -- the extraction ranker's
uniqueness floor (raised 0.5 -> 0.75) and a new entity-match guard on
the router's iframe tier (catches a shared third-party widget like
"Hopscotch" masquerading as the target place). Also fixed
`WebsiteImageExtractor`'s total lack of JS rendering with a
browser-escalation fallback.

**PR #118:** you asked me (via the user) to triple-check before
extending #117's fix elsewhere. Good thing -- tracing the actual call
graph found `MasterDataOrchestrator.ensure_place()` routes any
non-Grubhub place (the majority) through `ExtractionController` +
`MenuOrchestrator.run_with_items()`, which shares zero code with
`menu_extraction_router.py`. #117 never protected this path, and this
is the exact system `docs/PHASE_PLAN.md` prescribes as the current
Phase-4 tool (confirmed still actively maintained via your own PR #61,
merged 2 days before this session). Fixed it at the actual shared choke
point (`menu_pipeline.py`'s `_is_low_quality`, called by both
`run_for_place` and `run_with_items`) instead of duplicating checks into
`ExtractionController`. Also added a confirmation gate to
`run_phase4_batch.py` itself -- it previously had no preview mode, no
`--run` flag, and an optional/unbounded `--limit`.

## Verification (mine, local)

27 new tests total across both PRs, each regression-checked individually.
Full backend suite: 1014 passed, 2 skipped (987 baseline + 27 new).
Neither `menu_enrichment` nor `image_ingestion` is in the current
scheduler allowlist, and `run_phase4_batch.py` isn't scheduled at all --
none of this touched anything live.

## Known gaps / risks

- Entity-match (JSON-LD/title vs. place name) still isn't wired into
  `ExtractionController`'s path specifically -- it doesn't retain fetched
  HTML in its result. The duplicate-ratio gate added in #118 is the more
  broadly-protective fix and covers the confirmed incident's shape
  either way, but a future *different* contamination shape (not
  duplicate-heavy) on that path wouldn't be caught by name-matching.
- Code-level proof only, same as always -- production retry is the real
  test.

## Next action

Three independent things, whenever you're back:
1. Menu canary retry on Itani + a new small batch.
2. Image acquisition canary retry on the two zero-candidate sites.
3. If you ever run `run_phase4_batch.py` per the Phase 4 plan, it now
   needs `--limit N` (max 200) and `--run` -- preview first.

Plus the still-open `image_processing_recovery` synthetic test request
from before -- unrelated, any order.
