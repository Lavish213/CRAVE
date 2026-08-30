# H-20260830-population-readiness
Status: ready-for-review
Owner: Codex
Branch: codex/population-readiness-pass
Base SHA: f8a7f751d9837314ab02eeed326348db7d32249e
Commit SHA: 4ece444
Allowed next files: none until review

## Outcome
Audited place/menu/image population end to end and queried production read-only.
Fixed three proven blockers: same-name branches were forbidden by the canonical
unique constraint; menu provider/source/image lineage was discarded between
claims and publication; and Overture used obsolete release discovery while
converting source failures into successful empty runs. Added the migration,
regressions, menu API lineage, authoritative Overture STAC discovery, and
`docs/POPULATION_READINESS.md` with the baseline and capped rollout gates.

No production write, migration, deployment, or population job was run.

## Verification
- Targeted discovery/menu suite -> 57 passed.
- Full backend suite after all changes -> 822 passed, 2 skipped.
- Final Overture unit suite -> 8 passed.
- Fresh SQLite upgrade -> downgrade one revision -> upgrade head -> passed.
- `python -m alembic heads` -> `c3d4e5f6a7b8 (head)`.
- Read-only Overture sandbox -> release `2026-08-19.0`, 257 food places in a
  0.01-degree San Francisco bounding box.
- Read-only Railway evidence -> Overture repeatedly reported success with
  `fetched=0`; same-run OSM fetched 5,571 and 3,085.
- `git diff --check` -> clean.

## Known gaps / risks
- Existing menu rows need controlled re-materialization to backfill provider/
  image lineage; this preserves new or reprocessed truth only.
- No production Overture write was attempted. The one-city dry run and capped
  canary are deliberately still required.
- Overture/OSM/AllThePlaces/Foursquare records must be reconciled, not blindly
  unioned. Canonical source-observation/last-seen policy remains separate work.
- `app/services/truth/place_resolver.py` appears unused and references
  nonexistent `Place.phone` / `Place.category_id`; this branch does not use it.
- Price-tier coverage is zero. The guide rejects synthetic filling; a
  provenance-bearing, normalized menu-price derivation is later work.

## Next action
Inspect `git show 4ece444`, rerun the backend suite and migration, then review
the PR. If accepted, merge/deploy before only the documented one-city canary;
do not start a global population run.
