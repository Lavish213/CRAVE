# H-20260912-feed-decision-session

Status: ready-for-review
Owner: Codex
Branch: codex/feed-decision-session
Base SHA: 7bf81bda3dab274f00ec5db35c68c8235f7a3c2f
Commit SHA: 84f7cd6
Allowed next files: none pending PR review

## Outcome

Propagated the Foundation Gate contracts through Feed and Decision Session
without redesigning the approved hierarchy. Query keys and stale times now use
the shared contract; remote requests receive cancellation signals; malformed
payloads fail instead of becoming false empty states; personalized
recommendations use account-isolated TanStack Query state; stale/retry and
bounded-end states are explicit; the discovery tail no longer silently drops
valid candidates; and PlaceCard's Save control is no longer nested inside the
card control and now has a 44x44 target.

## Verification

- `npm test -- --runInBand __tests__/feed.test.tsx src/hooks/useDecisionSession.test.tsx src/hooks/useRecommendations.test.tsx src/api/decisionSession.test.ts --silent --forceExit` -> passed (4 suites, 25 tests).
- `npx tsc --noEmit --pretty false` -> passed.
- `npm test -- --runInBand --silent --forceExit` -> passed (51 suites, 541 tests).

## Known gaps / risks

- Reject/replace-only-rejected, the two-full-set-rejection prompt, context-chip
  direct asks, and a durable session identifier require a literal backend
  recommendation/session contract that the Feed doctrine explicitly lists as
  unresolved. They were not fabricated client-side.
- The personalized social rail remains blocked on its explicitly unresolved
  migration contract; the current friends feed is chronological.
- Device/E2E verification, PR CI/CodeQL, CodeRabbit, and final PR-head audit
  remain required before merge.

## Next action

Push/open the dedicated Feed PR, request review, inspect every check and
actionable finding, and perform a final audit of the actual PR head. Do not
merge silently.

---

# H-20260911-place-detail-proving-slice

Status: ready-for-review
Owner: Codex
Branch: codex/place-detail-proving-slice
Base SHA: 4d065c1
Commit SHA: aec75009b14b7609c0175e60d1e80b37636e3bea
Allowed next files: frontend/app/place/[id].tsx, frontend/__tests__/place-detail.test.tsx, .agent-bridge/STATE.md, .agent-bridge/codex-to-claude.md

## Outcome

Codex started the Place Detail proving slice from the locked Foundation Gate.
No visual redesign was introduced.

Changed Place Detail to:
- use `foundationQueryKey()` and `STALE_TIME` for the main place query,
  caller rankings query, and relationship query;
- share `https://crave.app/place/{id}` through `placeUniversalLink()` instead
  of making `crave://` the user-facing share URL;
- show honest hours provenance copy when an open/closed chip is rendered;
- label menu evidence as `Menu updated …` or `Menu freshness unknown` instead
  of implying every dated/undated menu is freshly verified.

Added focused test coverage for those contracts.

## Verification

- `npm test -- --runInBand __tests__/place-detail.test.tsx src/contracts/foundationGate.test.ts --silent --forceExit` → passed (`2 passed, 41 tests`).
- `npx tsc --noEmit --pretty false` → passed.
- `npm test -- --runInBand --silent --forceExit` → attempted; touched suites passed, but unrelated `__tests__/profile.test.tsx` failed on existing timeout/text-query flake.

## Known gaps / risks

- This does not build associated domains/web fallback hosting for
  `https://crave.app`; it switches Place Detail to the already-locked
  primary URL contract so infra can satisfy it.
- Place Detail still has additional side-loads (`craves`, friend rankings,
  menu) that are not fully migrated to React Query; this pass proves the
  contract on the primary route/query/link/provenance path.
- Full-suite green should be re-established after the unrelated Profile test
  flake is addressed or rerun in CI.

## Next action

Review and merge this Place Detail proving-slice PR. After merge, continue
the doctrine order toward Feed / Decision Session.

# H-20260911-foundation-gate-contracts

Status: ready-for-review
Owner: Codex
Branch: codex/foundation-gate-contracts
Base SHA: aef122e
Commit SHA: fe4765408e4a91157603c3ca803723b56fde98fb
Allowed next files: docs/doctrine/CRAVE_FRONTEND_EXECUTION_ORDER.md, docs/doctrine/CRAVE_FOUNDATION_GATE_CONTRACTS.md, frontend/src/contracts/foundationGate.ts, frontend/src/contracts/foundationGate.test.ts, .agent-bridge/STATE.md, .agent-bridge/codex-to-claude.md

## Outcome

Codex finished the remaining Foundation Gate contract layer without starting
Place Detail implementation or broad visual propagation.

Added:
- `docs/doctrine/CRAVE_FOUNDATION_GATE_CONTRACTS.md` covering the locked
  error taxonomy, React Query conventions, universal-link contract, and
  privacy/provenance scopes.
- `frontend/src/contracts/foundationGate.ts` with executable contract helpers
  for error presentation, query-key isolation/determinism, place universal
  links, and provenance display permissions.
- `frontend/src/contracts/foundationGate.test.ts` locking the contract
  behavior.
- A link from `CRAVE_FRONTEND_EXECUTION_ORDER.md` to the new contract doc.

## Verification

- `npx tsc --noEmit --pretty false` → passed.
- `npm test -- --runInBand src/contracts/foundationGate.test.ts --silent --forceExit`
  → `1 passed, 4 tests passed`.

Host disk is nearly full, so verification is limited to the sparse worktree
and targeted frontend checks; full CI should run on PR.

## Known gaps / risks

- This is contract/invariant work only. It does not migrate screens to React
  Query, implement associated domains/web fallback, or render provenance-aware
  Place Detail copy.
- Full repo checkout/full backend suite is blocked locally by host disk space.

## Next action

Review and merge this contract PR. After merge, the next frontend lane is
Place Detail proving slice under `CRAVE_FRONTEND_EXECUTION_ORDER.md`.

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
# H-20260912-food-evidence-add-spot-hardening

Status: ready-for-review
Owner: Codex
Branch: codex/food-evidence-add-spot-hardening
Base SHA: 7bf81bda3dab274f00ec5db35c68c8235f7a3c2f
Commit SHA: bf63470 (plus final handoff commit)
Allowed next files: none until independent review

## Outcome

Hardened Food Evidence / Add Spot without redesign: account-scoped durable
draft ownership, awaited attachment before Place Detail navigation, visible
retry for failed attachment, synchronous duplicate-capture protection, and
visible picker/camera failures. Full defect/defer rationale is in
`docs/audits/FOOD_EVIDENCE_ADD_SPOT_GAP_LOG_2026-09-12.md`.

## Verification

- `npx tsc --noEmit --pretty false` → passed.
- `npm test -- --runInBand __tests__/food-evidence.test.tsx __tests__/add-spot.test.tsx src/stores/postingDraftStore.test.ts --silent --forceExit` → 3 suites passed, 38 tests passed.
- `npm test -- --runInBand --silent --forceExit` → 51 suites passed, 540 tests passed.

## Known gaps / risks

- Physical-device camera/location/accessibility certification was not
  available locally.
- Location-free manual search, anonymous draft migration, full Posting V2
  publish/visit semantics, and Dish Intelligence remain deliberately deferred
  pending approved contracts/dependencies.

## Next action

Review the dedicated PR and its CI/CodeRabbit status; do not merge from this
handoff.

---
