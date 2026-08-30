# H-20260829-extraction-observability
Status: ready-for-review
Owner: Codex
Branch: codex/extraction-observability-pass
Base SHA: 3b9eb15d8d669711bf97575de6d03ee7c27f1ba2
Commit SHA: 554c013
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
The production queue now rejects malformed pseudo-URLs, prefers direct menu and
provider sources over locator pages, and prefers fresh attempts over exhausted
retries. A shared source normalizer prevents a malformed preferred URL from
hiding a valid fallback. Finally, a live no-write provider probe exposed that
the registry passed `(url, html)` into legacy `(html, url)` adapters and passed
two arguments into one-argument direct adapters. The registry now normalizes
both contracts. A real Square page that returned zero through the router before
the fix returned 21 named and priced items afterward.

Follow-up live validation found ChowNow's menu nested as schema.org
Restaurant/Menu/MenuSection/MenuItem JSON-LD. The shallow walker emitted
containers instead of usable leaves; the recursive walker now returns 126 real
items and preserves section names. A Toast page returned 112 items live.
Clover's old URLs redirect to a new React/Flight storefront the adapter does
not parse, and Popmenu has no production sample corpus; neither is claimed as
working.

The Feed-image trace found three production defects. Google extraction emits
safe bare `places/.../photos/...` references, but ImageMatcher rejected every
non-HTTP value although the proxy/downloader/persistence layers support that
format. ImageWorker selected partial galleries while ImageIngestService skipped
anything with one existing image, causing repeated false progress. Successful
forced recovery also never cleared failure/block state. Red-first regressions
cover all three. ImageReader now tries free provider/official-site sources
first and calls paid Google only below three unique usable free URLs.

## Verification
- focused endpoint relevance regression -> failed before the fix, then `2 passed, 8 deselected`
- extraction/observability/population selection -> `27 passed in 0.99s`
- provider contract regressions -> failed `2` before the fix, then `2 passed`
- menu population/worker/observability regressions -> `31 passed`
- `/Users/angelowashington/CRAVE/venv/bin/python -m pytest -q` -> `847 passed, 3 failed, 3 skipped`; the three failures were unrelated streak tests crossing the UTC/Pacific date boundary
- `TZ=UTC /Users/angelowashington/CRAVE/venv/bin/python -m pytest -q` -> `850 passed, 3 skipped, 32 warnings in 10.86s`
- `python scripts/run_menu_extraction_corpus.py --manifest tests/fixtures/menu_extraction/manifest.json --json` -> `4 passed, 0 failed` (including navigation-only negative fixture)
- `DATABASE_URL=sqlite:///./test_crave.db python scripts/populate_menus.py --limit 3 --json` -> previewed one candidate and stated no writes performed
- `python -m compileall -q app scripts/populate_menus.py scripts/run_menu_extraction_corpus.py` -> exit 0
- `git diff --check` -> exit 0
- Railway production preview, Oakland limit 10 -> 10 candidates, all at four
  failures; no writes. One malformed bare source (`SpritzersCafe`) was exposed.
- Railway production preview, Alameda limit 10 -> 10 first-attempt candidates;
  no writes. Most were chain locator pages rather than direct menu URLs.
- Railway discovery dry-run, limit 20 -> live baseline `57,669` items and
  `928/34,934` active places (2.7%); found seven Toast/Square sources, no writes.
- read-only extraction probe of those seven sources -> all initially returned
  zero through the provider registry, exposing the adapter contract defect.
- corrected router + fetched public Viva Tacos Square page -> 21 structured
  items, including names and cent-denominated prices; no DB writes.
- live ChowNow page after recursive JSON-LD fix -> 126 items with sections;
  live Toast page -> 112 items; no DB writes.
- focused image/provider suite -> `82 passed, 8 warnings`.
- final `TZ=UTC ... pytest -q` -> `866 passed, 3 skipped, 32 warnings in 7.19s`.
- production image counts (read-only): 34,934 active; 20,646 zero-image;
  20,648 no-primary; 1,909 blocked; only 117 both blocked and image-empty.
- 1,792 blocked places already have >=3 images and one primary, proving stale
  block state survived later success.
- the latest 12 scheduler jobs each reported the identical
  `processed=100, succeeded=100, images_written=177`, corroborating churn.
- 7,872 zero-image places have an official website available for free-first
  extraction before Google fallback.
- No-write/no-LLM probe after the endpoint fix -> MOD Pizza HTTP 200 / 0 items,
  Chipotle HTTP 200 / 0 items, Cafe Jolie HTTP failure; no unrelated endpoint
  spray appeared.

## Known gaps / risks
- This branch is stacked on PR #53 / commit `3b9eb15`; review and merge that dependency first or retarget after it lands.
- The replay corpus contains four representative fixtures, not a claim of live-catalog coverage.
- No production population was executed. Live previews show candidate-source
  quality is materially better after the queue change, but requires independent
  review before the explicitly confirmed command.
- Clover needs a separate React/Flight adapter migration; Popmenu remains
  unvalidated because production has no sample URLs.
- ChowNow and Toast samples exposed zero item-level images. This image fix
  improves place/feed coverage, not menu-item photo coverage.
- The 117 image-empty blocked places need an independently reviewed, bounded
  retry decision after deployment; this branch makes no production mutation.
- The discovery sample's 7/20 hit rate is biased toward known-provider URLs and
  must not be projected across all active places.
- Full-suite warnings are pre-existing Pillow deprecation and test JWT key-length warnings.

## Next action
Independently inspect commits `1684b20..554c013`, rerun the full backend suite
with a stable test timezone and the replay corpus, then review the stacked PR.
Confirm provider behavior and all image-pipeline changes. Do not run live
population or image backfill as part of review.
