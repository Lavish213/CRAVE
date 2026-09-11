# H-20260910-ui-v2-mock-screens

Status: ready-for-review
Owner: Codex
Branch: codex/ui-v2-mock-screens
Base SHA: 8d3023d594f40f8d90de93683b59c1c714f7d407
Commit SHA: pending PR head
Allowed next files: frontend/app/(tabs)/index.tsx, frontend/src/screens/SearchScreen.tsx, frontend/src/screens/MapScreenCore.tsx, frontend/src/components/MapBottomSheet.tsx, frontend/app/settings.tsx, frontend/src/constants/colors.ts, frontend/src/components/CraveV2.tsx, .agent-bridge/STATE.md, .agent-bridge/codex-to-claude.md

## Outcome

Codex implemented the first real CRAVE UI V2 mock-screen slice in the Expo
frontend, using the frozen dark/warm Search/Map north-star language without
claiming full 16-state certification.

What changed:
- Added shared V2 primitives/tokens (`CraveV2.tsx`, warm/dark color tokens).
- Reworked Home/Feed into a food-led V2 shell while preserving real feed,
  saves, decision-session roles, impressions, and filtering.
- Reworked Search home/results into the appetite-forward V2 direction with
  dominant answer hierarchy, alternatives, reason labels, recent searches,
  shortcuts, and existing submit/relaxation behavior preserved.
- Reworked Map overlays and selected-place card toward the V2 visual language
  while preserving Map candidate ownership, selection, saved state, and
  instrumentation behavior.
- Reworked Settings shell to match the same CRAVE visual direction while
  preserving existing notification/account/delete behavior.
- Follow-up truth audit removed static Unsplash placeholder hero/map images,
  removed the false `Oakland, CA` fallback when no city/location exists, and
  made the Map selected-card context label mode-specific instead of always
  claiming `Search-owned candidate`.
- Research-backed accessibility/interaction pass separated `V2PlaceCard`'s
  open-place and save actions into distinct touch/accessibility targets, raised
  Search clear/removable-constraint controls to 44pt minimums, and measured V2
  token contrast.

## Verification

From `frontend/`, using a temporary local `node_modules` symlink to the main
checkout dependencies, then removing it afterward:

- `npx tsc --noEmit` → passed.
- `npm test -- --runInBand __tests__/feed.test.tsx __tests__/search.test.tsx __tests__/search-decision-support.test.tsx __tests__/map.test.tsx __tests__/map-instrumentation.test.tsx __tests__/settings.test.tsx --silent --forceExit`
  → `6 passed, 82 tests passed`.
- `npm test -- --runInBand --silent --forceExit`
  → `50 passed, 522 tests passed`.
- Static scan across touched implementation files for mock/static north-star
  leakage (`HERO_FOOD_IMAGE`, `MAP_TEXTURE_IMAGE`, `unsplash`,
  `Search-owned candidate`, `Oakland, CA`, `mockup`, `fake`, `hardcoded`) →
  no remaining matches.
- V2 contrast spot-check: `craveMuted` is at least `7.88:1` on V2 dark
  surfaces; `craveCream`, `craveGold`, `craveGoldDeep`, `craveGreen`, and
  `error` all exceed AA normal-text contrast on the V2 dark surfaces.

## Known gaps / non-claims

- Not device/simulator verified yet.
- Not a full 16-state Search/Map propagation or runtime accessibility proof.
- Real-photo torture testing remains pending; production imagery may expose
  additional composition issues.
- Native map marker hit geometry/non-color selected-state behavior still needs
  simulator/device verification.
- Jest still needed `--forceExit` due the existing open-handle behavior in
  this frontend test environment.

## Next action

Review the PR visually and on device/simulator. If accepted, follow with a
separate Search/Map resilience/accessibility propagation branch rather than
expanding this first implementation slice.

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
