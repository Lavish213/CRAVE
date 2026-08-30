# Production population canary — 2026-08-30

## Verdict

**HOLD — staged safely, not released.** Ten Oakland Overture records are in
production as blocked, unresolved `DiscoveryCandidate` rows. They cannot be
picked up by the promotion worker or appear in the app. The batch proved that
Overture is useful for coverage, but unsafe to auto-promote without current
existence and entity-resolution checks.

Batch ID: `oakland-20260830-a`

## Preflight evidence

- Public `/health` returned `status=db=cache=worker=ok`.
- Railway web service and Postgres were online.
- Alembic production current and repository head both reported
  `c3d4e5f6a7b8`.
- Backend suite after the canary tooling and menu guard: `880 passed,
  3 skipped`.
- Tiny live Overture schema check succeeded. The final city-centered preview
  fetched 769 food-and-drink records from a 0.01-degree Oakland box.

## Before/stage measurements

Fresh read-only production measurements (the background workers make these
counts live rather than immutable):

| Metric | Result |
| --- | ---: |
| Active places | 37,763 |
| Active places with address | 15,427 (40.9%) |
| Active places with website | 14,132 (37.4%) |
| Active places with `has_menu` | 942 (2.5%) |
| Active published menu items | 58,241 |
| Overture candidates before canary | 0 |
| Overture candidates staged | 10 |
| Staged rows blocked | 10 / 10 |
| Staged rows resolved/promoted | 0 / 10 |
| Selected with address/category | 10 / 10 |
| Selected with website | 8 / 10 |
| Likely duplicates within 100m | 5 / 10 |

## Manual sample findings

- `Odin`, `NIDO Kitchen & Bar`, `Good Vybes & Brews`, `Tiger's Taproom`, and
  `Oakland United Beerworks` were probable matches or historical aliases of
  existing records. Official/current pages confirmed that the original NIDO
  at 444 Oak is now ODIN.
- `North Beach Sandwicheez` and Good Vybes had current first-party or local
  district evidence at their exact addresses.
- The 66 Franklin `Forge Pizza` record is stale: current first-party material
  says the Jack London location moved to Rockridge.
- The sample also contained records whose nearest existing place was unrelated,
  proving proximity alone is not an entity match.

This mix is why the staged rows remain blocked. Monthly bulk data is a strong
candidate source, not proof that a venue is currently open or a new entity.

## Other blockers found by the readiness audit

1. `run_phase4_audit.py` referenced nonexistent `menu_items.price`; corrected
   to canonical `price_cents` on this branch.
2. Two published zero-price POS artifacts named `Test`/`test` were visible.
   The publisher now rejects only exact placeholder-style names with no positive
   price and no description. Existing places must be republished after this
   change deploys to remove the two cached rows.
3. 2,530 legacy external images lack Phase 3 content/quality classification.
   Dry-run distribution: 2,418 gallery-only, 110 hidden, 2 candidate-primary;
   90.3% classify as unknown. Do not execute that backfill until its low-signal
   result is reviewed—classification would mostly encode URL/position
   heuristics, not real visual understanding.
4. Existing menu items have zero populated `provider` values. The provenance
   fix is deployed, but historical truth must be rematerialized in bounded
   batches before coverage changes.

## Rollback

The exact batch rollback is intentionally guarded:

```bash
cd backend
python3 scripts/run_overture_canary.py \
  --rollback-batch oakland-20260830-a \
  --confirm ROLLBACK_OVERTURE
```

It deletes only Overture rows carrying this batch marker while they remain
blocked, unresolved, and without a promoted place ID. Verification after
staging found exactly 10 matching rows.

## Required next gate

Before releasing any staged candidate:

1. classify as existing match, renamed/moved/closed, or genuinely new;
2. require current first-party or municipal corroboration for new/active status;
3. merge aliases into the existing entity rather than create a duplicate;
4. reject or retain blocked any stale/closed record;
5. release no more than five confirmed-new records, then verify Feed, Search,
   Map, and Place Detail before expanding the city box.
