# H-20260909-menu-provenance-fix

Status: ready-for-review
Owner: Codex
Branch: codex/menu-provenance-fix
Base SHA: a271856a71fdcda47619178eed6f17e6fdce6eb0
Updated base SHA: 8d3023d594f40f8d90de93683b59c1c714f7d407
Verified code SHA: 988c98491af1af8f6a761739dd870142db345392
Allowed next files: backend/app/services/menu/contracts.py, backend/app/services/menu/menu_pipeline.py, backend/app/services/menu/materialize_menu_truth.py, backend/app/services/menu/menu_publisher.py, backend/app/services/menu/claims/menu_claim_emitter.py, backend/app/services/menu/claims/menu_claim_values.py, backend/app/services/menu/processing/menu_orchestrator.py, backend/app/services/menu/orchestration/menu_enrichment_worker.py, backend/tests/test_menu_provenance_pipeline.py, .agent-bridge/STATE.md, .agent-bridge/codex-to-claude.md

## Outcome

Codex investigated the menu canary provenance failure found during immediate
review of the reviewed 10-place production canary. The canary materialized two
menus, but every published item lacked source URL provenance, so both were
reverted immediately; net retained publish count is zero.

Root cause: downstream materialization/publishing already preserved lineage
when `PlaceClaim.value_json` contained `provider`, `source_type`, and
`source_url`. The loss happened earlier: `process_extracted_menu()` stripped
lineage while converting extracted items into canonical items, and
`emit_menu_claims()` used only a function-level `source_url`, so item-level
source URLs never reached claim payloads. The enrichment worker had the same
canonical-to-normalized lineage drop.

Fix:
- `CanonicalMenuItem` now carries `provider_item_id`.
- `process_extracted_menu()` preserves `image_url`, `provider`,
  `provider_item_id`, `source_type`, and `source_url`.
- `MenuOrchestrator` and the enrichment worker preserve that lineage when
  rebuilding `NormalizedMenuItem` objects.
- `emit_menu_claims()` prefers each item's own source URL and falls back to
  the caller's source URL.
- Anonymous menu claims are refused when neither the item nor caller provides
  a source URL, preventing `"unknown-source"` claims from materializing into
  public menu truth.
- `build_menu_claim_payload()` falls back to item-level source/provider/type
  and provider item ID.
- `materialize_menu_truth()` maps stored claim `external_menu_id` back to
  canonical `provider_item_id` and serializes it into menu truth.
- `MenuPublisher` keeps `source_url` and `provider_item_id` together in
  `MenuItem.raw_payload`.
- `MenuOrchestrator` applies the place probe URL only as an all-items-missing
  fallback, so mixed-source batches keep item-bound source URLs.

## Verification

- `python3 -m pytest backend/tests/test_menu_provenance_pipeline.py backend/tests/test_menu_pipeline_quality_gate.py backend/tests/test_menu_extraction_heuristics.py backend/tests/test_menu_extraction_observability.py backend/tests/test_menu_source_success_semantics.py -q`
  → `38 passed in 0.92s`
- `python3 -m compileall backend/app/services/menu` → clean

## Known gaps / risks

- No new production menu publish canary was run after this fix. That should
  wait until review/merge and fresh explicit human authorization.
- The earlier OSM backfill production run remains partially applied exactly as
  recorded below; this provenance fix does not run or resume it.

## Next action

Review and merge this branch, then run a new reviewed 10-place menu canary
from merged `main`. Immediately verify every materialized item has source URL
provenance before retaining the publish.

# H-20260909-osm-backfill-dedupe-blocker

Status: blocked
Owner: Codex
Branch: codex/osm-backfill-dedupe-claims
Base SHA: 2bd1bfa1d29700c9894cf64face90cf138529c9f
Commit SHA: bc92ea70a7d11ef4e0776987ac8c77b6cbdd20cf
Allowed next files: backend/scripts/backfill_osm_hours_and_seating.py, backend/tests/test_backfill_osm_hours_and_seating.py, .agent-bridge/STATE.md, .agent-bridge/codex-to-claude.md

## Outcome

Codex verified Railway production access and attempted the approved OSM
hours/outdoor-seating backfill from a clean `origin/main` worktree.

Dry-run on merged `main` was sane: `11239` OSM candidates scanned, `4321`
claims would be written across `3658` places. The real run then started and
committed the first small batches, reaching `30` claims across `27` places,
before failing in a later batch on the existing `(place_id, field, claim_key)`
uniqueness constraint.

Root cause: the script checked for claims already committed in the database,
but did not dedupe claims scheduled within the same run/session. Production
has duplicate promoted OSM candidates that can point to the same place and
produce the same deterministic claim before the session flushes.

This branch fixes that by keeping an in-memory `(place_id, field, claim_key)`
set for claims already scheduled in the current run, and adds a regression
test for duplicate OSM candidates resolving to the same place.

The menu backlog canary was not run. Current `run_menu_backlog_canary.py`
requires exact `--place-ids` or `--place-ids-file`; the bare
`--run --confirm-count 10` command is insufficient without a reviewed 10-place
ID list.

## Verification

- `railway status` in the main repo → production project/service linked.
- clean worktree from `origin/main` → `2bd1bfa1d29700c9894cf64face90cf138529c9f`.
- `railway run --no-local --service CRAVE-scheduler --environment production -- sh -lc 'if [ -n "$DATABASE_URL" ]; then echo DATABASE_URL_PRESENT; else echo DATABASE_URL_MISSING; fi'` → `DATABASE_URL_PRESENT`; value was not printed.
- `railway run --no-local --service CRAVE-scheduler --environment production -- sh -lc 'cd backend && python3 scripts/backfill_osm_hours_and_seating.py --dry-run'` on merged `main` → completed with `candidates_touched=3663 claims_written=4321 places_affected=3658 dry_run=True`.
- `railway run --no-local --service CRAVE-scheduler --environment production -- sh -lc 'cd backend && python3 scripts/backfill_osm_hours_and_seating.py'` on merged `main` → failed after early committed batches with `psycopg2.errors.UniqueViolation` on `(place_id, field, claim_key)`.
- `python3 -m pytest backend/tests/test_backfill_osm_hours_and_seating.py -q` after fix → `5 passed in 0.43s`.
- Patched production dry-run → completed with `candidates_touched=3634 claims_written=4289 places_affected=3631 dry_run=True`.

## Known gaps / risks

- Production is partially backfilled: the early committed batches wrote `30`
  claims across `27` places before the failing batch rolled back.
- The remaining production write should not be run from this unmerged branch
  unless the human explicitly authorizes that shortcut.
- Menu canary still needs a reviewed exact 10-place ID list before it can run.

## Next action

Review and merge `bc92ea70a7d11ef4e0776987ac8c77b6cbdd20cf`, then rerun the
OSM backfill for real from merged `main`. For the menu canary, produce/review a
10-place ID file first, preview it, then run with
`--place-ids-file <reviewed-file> --run --confirm-count 10`.
