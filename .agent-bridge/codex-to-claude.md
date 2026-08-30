# H-20260830-map-truth-clustering
Status: ready-for-review
Owner: Codex
Branch: codex/map-truth-and-clustering
Base SHA: f8a7f751d9837314ab02eeed326348db7d32249e
Commit SHA: e26e67a
Allowed next files: review only; no edits until ownership is acknowledged

## Outcome
The live iPhone 17 Pro Map rendered a nearly unusable cloud for a 250-place
response. This commit replaces the longitude grid with density-aware,
screen-space collision clustering; preserves progressive street-level pin
reveal; adds accessible pin/cluster labels; makes map tiers stable across
viewport changes by using city rank percentiles; and turns DB/query failures
into retryable 503s instead of false empty catalogs. If a later viewport fetch
fails, retained pins are explicitly labeled as previously loaded.

## Verification
- `/Users/angelowashington/CRAVE/venv/bin/pytest -q tests/test_map_query.py tests/map/test_map_geojson.py tests/map/test_map_error_contract.py` → 11 passed
- `/Users/angelowashington/CRAVE/venv/bin/pytest -q` → 819 passed, 3 skipped
- `npm test -- --runInBand __tests__/map.test.tsx` → 11 passed
- `npx tsc --noEmit` → clean
- `npm test -- --runInBand` → 31 suites / 301 tests passed; Jest then hit the repository's known open-handle hang and the idle process was interrupted (exit 130) after the complete pass summary
- Native branch loaded 250 real production Map features on iPhone 17 Pro Simulator. Before: `/private/tmp/crave-map-audit-01.png`. Final: `/private/tmp/crave-map-after-collision-clustering.png` (roughly a dozen separated clusters, no original marker cloud).
- `git diff --check` → clean

## Known gaps / risks
- The Expo Simulator displays the known notification entitlement error toast; this is not caused by Map and obscures the bottom tab bar in the screenshot.
- Cluster counts cover the API's capped 250 returned places, not the entire catalog. A later server-side aggregation/truncation contract is still needed for exact whole-city counts.
- This is a verified logic/usability repair, not the final CRAVE visual redesign. Search↔Map state synchronization, a deliberate “Search this area” interaction, and selected-place decision-card content remain product/design work.
- Population PR #56 remains separately blocked on independent review; no migrations, deployment, or production population writes were performed here.

## Next action
Fetch `codex/map-truth-and-clustering`, inspect `e26e67a`, rerun the focused
checks, compare the native before/after screenshots, and review the PR before
merge.
