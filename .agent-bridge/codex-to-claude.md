# H-20260829-extraction-observability
Status: ready-for-review
Owner: Codex
Branch: codex/extraction-observability-pass
Base SHA: 3b9eb15d8d669711bf97575de6d03ee7c27f1ba2
Commit SHA: 14dbd68
Allowed next files: none until independent review

## Outcome
Repaired 22 stale `ExtractedMenuItem(price=...)` call sites through one
price-to-cents normalizer; added three deterministic offline extraction
fixtures; taught JS endpoint memory to retain only endpoints whose own payload
produced plausible menu items; added snapshot coverage/fingerprint/drift
evidence and aggregate regression diagnostics; and added a bounded,
city-scoped, preview-first population CLI that reuses the real MenuWorker.
Execution requires both `--execute` and exact `--confirm POPULATE`. Also fixed
the existing manual trigger passing an unsupported orchestrator keyword. An
adversarial follow-up makes the corpus fail on inflated item counts, adds a
navigation-only page that must yield zero items, and proves preview/bad
confirmation leave population state unchanged.
Live preview probes then exposed generic JS endpoints being replayed solely
because their host contained `api` (Mapbox, form-submit APIs, tracking/error
URLs, and `404.gif`). A red-first regression now requires an actual menu,
catalog/product/item, known-provider, or GraphQL signal before endpoint replay.

## Verification
- focused endpoint relevance regression -> failed before the fix, then `2 passed, 8 deselected`
- extraction/observability/population selection -> `27 passed in 0.99s`
- `/Users/angelowashington/CRAVE/venv/bin/python -m pytest -q` -> `844 passed, 3 skipped, 32 warnings in 8.21s`
- `python scripts/run_menu_extraction_corpus.py --manifest tests/fixtures/menu_extraction/manifest.json --json` -> `4 passed, 0 failed` (including navigation-only negative fixture)
- `DATABASE_URL=sqlite:///./test_crave.db python scripts/populate_menus.py --limit 3 --json` -> previewed one candidate and stated no writes performed
- `python -m compileall -q app scripts/populate_menus.py scripts/run_menu_extraction_corpus.py` -> exit 0
- `git diff --check` -> exit 0
- Railway production preview, Oakland limit 10 -> 10 candidates, all at four
  failures; no writes. One malformed bare source (`SpritzersCafe`) was exposed.
- Railway production preview, Alameda limit 10 -> 10 first-attempt candidates;
  no writes. Most were chain locator pages rather than direct menu URLs.
- No-write/no-LLM probe after the endpoint fix -> MOD Pizza HTTP 200 / 0 items,
  Chipotle HTTP 200 / 0 items, Cafe Jolie HTTP failure; no unrelated endpoint
  spray appeared.

## Known gaps / risks
- This branch is stacked on PR #53 / commit `3b9eb15`; review and merge that dependency first or retarget after it lands.
- The replay corpus contains four representative fixtures, not a claim of live-catalog coverage.
- No production population was executed. Live previews show candidate-source
  quality must be improved or reviewed before the explicitly confirmed command:
  retry-exhausted Oakland sources and Alameda chain locator pages are poor
  first-write candidates.
- Full-suite warnings are pre-existing Pillow deprecation and test JWT key-length warnings.

## Next action
Independently inspect commits `1684b20..14dbd68`, rerun the full backend suite
and corpus, then review the stacked PR. Confirm the endpoint gate does not drop
real provider/menu endpoints. Do not run live population as part of review.
