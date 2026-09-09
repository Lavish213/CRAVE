# Active agent state

Status: ready for review
Owner: Codex
Branch: codex/free-source-coverage
Base SHA: 1d0339de555f3f733ebac70996b8b79c962f4b4e
Scope: Improve bounded free-only image acquisition recall using structured website/provider metadata, with candidates remaining hidden and review-gated.
Locked files: backend/app/services/images/website_image_extractor.py, backend/app/services/images/provider_image_extractor.py, backend/scripts/run_free_image_canary.py, backend/tests/test_website_image_extractor.py, backend/tests/test_free_image_canary_script.py, .agent-bridge/STATE.md, .agent-bridge/codex-to-claude.md
Verification plan: Reproduce current low-recall fixtures, add regression fixtures for authoritative structured metadata/provider assets, run focused image/canary tests, full backend suite, then a maximum-10-place production canary with no Google calls and hidden-only writes.
Explicit exclusions: Existing dirty checkout and all frontend/design files; paid Google acquisition; automatic public promotion; bulk image worker; menu pipeline changes; OSM hours/seating backfill.
Implementation commit: f63cd5a (`Improve free website image discovery`).
Verification: focused image/canary suite 25 passed; full backend suite 1112 passed, 2 skipped; production free-only canary staged 32 rows across 4/4 exact targets, independently rechecked as 32 hidden and 0 primary.
Known gap: Candidates remain review-gated; no automatic public promotion was attempted. Provider-claim expansion was investigated and intentionally not broadened because menu item photos already flow through the dedicated menu-image bridge and generic recursive harvesting would increase contamination risk.
Next action: Open the PR, request CodeRabbit review, resolve every actionable finding, then merge only after checks are green.

## Wave 6 — Craves intelligence — COMPLETE

All 4 steps merged: (1) backend + typed client, PR #215; (2) screen
rebuild around the reasoned subset, PR #216; (3) automatic cuisine/
geography clustering, PR #218; (4) doctrine correction reclassifying
contract §11 as blocked on §3.6 (operational-data ingestion, app-wide,
not Craves-specific), PR #219. Contract status: **GREEN**. One tracked,
non-blocking gap remains: the "Craves"/"Added" sections still render via
their own bespoke row style, not `PlaceCardCompact`, pending `/craves`
and `/hitlist/me` returning full `PlaceOut` instead of bare IDs.

## Wave 7 — Place Detail relationship hierarchy — COMPLETE

Per `docs/doctrine/CRAVE_MASTER_CODEX_REMAINING_WORK.md` §3.5 and
`docs/doctrine/CRAVE_SCREEN_CONTRACT_PLACE_DETAIL.md`. Three PRs:

1. **Backend groundwork — PR #221.** `visit_evidence_for_place()`
   single-place lookup; `reason_role`/`reason_source`/
   `visit_confirmation_count` columns on `HitlistSave` (the latter a
   real repeat-visit signal, incremented only on the `visited`
   False→True transition -- not fabricated from data that didn't
   support it); new `GET /place/{id}/relationship` endpoint (per-viewer,
   never cached, same pattern as the existing `.../friends` endpoint).
2. **Frontend rebuild — PR #222 (+ follow-up fix, this PR).** Four
   relationship modes real and distinct in the running app; shared
   `DecisionStrip` reused for a reason threaded from Craves/Search/
   Feed's Decision Session card via new `reason_role`/`reason_source`
   nav params, AND remembered on a later cold visit via the persisted
   `HitlistSave` fields (contract §13 -- the nav-param-only version
   shipped in #222 was a real gap, closed same-day rather than left
   silently incomplete); adaptive CTA ladder (Directions → "Save for
   tonight" → existing rank CTA once visited, relabeled "Rank it").
3. **Doctrine correction (this PR)** to
   `CRAVE_SCREEN_CONTRACT_PLACE_DETAIL.md` §22/§26, documenting what
   shipped precisely against the contract's own text and naming every
   simplification, not just the two blockers known up front:
   - **Reserve CTA rung** -- not attempted; no reservation-provider
     integration exists, and full reservations/ordering integration is
     **permanently** out of scope for V1 (`CRAVE_MASTER_CODEX_
     REMAINING_WORK.md` §4), not a "not yet built" item.
   - **§12's 4-action taste-correction vocabulary** -- not attempted;
     needs the Gate 2 taste graph, which doesn't exist.
   - **Quick-Take Reaction control** ("How was it?", §11/§14) --
     genuinely doesn't exist anywhere in the app (no data model, no
     UI). Wave 7 goes straight from "visited" to the existing "Rank it"
     CTA rather than fabricate a reaction control with nothing behind
     it. New finding (not in the original scoping) -- likely lands with
     Wave 8's posting composer "quick take" step
     (`CRAVE_MASTER_CODEX_REMAINING_WORK.md` §3.11), tracked there.
   - **§14's relationship-status copy** is simplified vs. the
     contract's exact spec ("visited N days ago" + reaction status) --
     ships as a visit-count-based headline instead, since the reaction
     status half depends on the Quick-Take control above.
   - "Regular"'s threshold is implemented at 2 confirmed visits, not
     the contract's own illustrative "10+" -- explicitly permitted by
     the contract's own text as a tuning detail, not a deviation.

Contract status: **YELLOW, unchanged** -- the real named blockers
(Dish Intelligence, Gate 2, `hours` ingestion, now also the Quick-Take
control) gate specific sections, not the whole contract, same as
before Wave 7. Full verification each PR: `tsc --noEmit` clean, full
frontend suite green (twice, parallel + `--runInBand`), backend suite
1076+ passed against local Postgres with migration upgrade/downgrade/
re-upgrade verified.

**Wave 8 (Posting/Private Logging) is not claimed by this session.**
Per `docs/CLAUDE_EXECUTION_BRIEF_WAVES_7_10_2026-09-08.md`'s own
handoff intent -- read that doc's Wave 8 section, the full Posting
Screen Contract (draft one first if it doesn't exist yet, following the
same audit process used for Search/Craves/Place Detail), the Privacy
Matrix, Evidence Hierarchy, and API contracts before claiming it here.

## What this supersedes

This file previously tracked Phases 1-7 production hardening and release
certification in long-form detail. That work is real and merged but is
compacted here per protocol ("keep inboxes short, move detail to the PR or a
dated archive") since a much larger, newer workstream has since completed and
is now the controlling context.

- Phases 1-7 hardening: merged (Phase 7 PR #138, SHA `ee77d302...`).
- Release-certification prep (Master Matrix, runbooks, credential/Sentry
  audits): merged, tracked in `docs/MASTER_RELEASE_CERTIFICATION_MATRIX.md`.
  Not re-summarized here — read that file directly if resuming that thread.
- Full product-doctrine workstream (V1 Scope through the Canonical
  Implementation Index, all PRs #148-#173): **complete, merged to `main`**.
  Do not re-open or redraft any of these without a proven doctrine gap or
  explicit new user direction.
- Implementation **Wave 3 — navigation topology** (PR #185) and **Wave 4 —
  Feed / Decision Session hierarchy**: both merged. Details in
  `docs/doctrine/CRAVE_CODEX_HANDOFF_STATE.md`.

## Full end-to-end verification (Claude, 2026-09-07, against main post-Wave-4)

Ran the actual CI commands locally, not just read the docs:
- Backend: `python -m compileall app` clean; `import app.main` clean;
  `pytest -q` → **1043 passed, 2 skipped**, 0 failures.
- Backend/Postgres invariant: `alembic heads` → exactly one head.
- Frontend: `npx tsc --noEmit` → **0 errors**.
- Frontend: `npx jest --ci` → **45/45 suites, 426/426 tests passed**.
- Repo-wide conflict-marker guard (the same grep CI runs) → clean.
- Cross-checked every YELLOW blocker in `CRAVE_CODEX_READINESS_AUDIT.md` §3
  against its source screen contract and `CRAVE_API_INTEGRATION_CONTRACTS.md`
  — every one is a genuine engineering/data-capability gap, not a hidden
  product-decision punt. Two cosmetic doc issues flagged, not fixed (low
  priority): some screen contracts still say "deferred to the *forthcoming*
  API/Integration Contract artifact" (that artifact now exists); 4 of 15
  contracts fold "unresolved dependencies" into Traceability's "Forward
  dependencies" line instead of using the mandatory standalone heading —
  content is present and correct either way.

**Net result: whole app (both halves) is green end-to-end on the current
main commit.** No regressions found through Wave 4.

## Wave 5 Search Screen Contract certification (Claude, 2026-09-07)

Wave 5 was originally merged as one commit (`37bebcf`, "Wave 5 semantic
Search and contextual Map") reported as fully finished. Auditing it
against `docs/doctrine/CRAVE_SCREEN_CONTRACT_SEARCH.md` line-by-line
surfaced real gaps one at a time rather than all at once — each was
fixed and merged before moving to the next, per explicit user direction
not to certify over a known gap:

- PR #190: the default GitHub CodeQL check (distinct from this repo's
  custom `Analyze` jobs — a real, repo-specific gotcha) had 3 open
  high-severity `js/insecure-randomness` alerts on `Math.random()`-based
  search-session ids. Replaced with `expo-crypto`'s `randomUUID()`.
- PR #191: the contract's Reason Block labeling requirement ("Best
  match for you / Safer pick / Worth exploring") was entirely unbuilt.
  Implemented via the shared `DecisionStrip` renderer with a
  Search-specific `SearchReasonRole` type kept structurally separate
  from Decision Session's `DecisionRole` — tested to confirm no
  vocabulary leakage either direction.
- PR #192: zero-state had no real decision-support content (contract
  §5/§6) and zero-result messaging was a generic "try broader terms"
  (contract §11, explicitly prohibited by §16). Implemented a
  time-relevant intent shortcut, recent-searches store, and named
  soft-constraint relaxation that never touches a dietary/allergy hard
  constraint.
- PR #193: a final line-by-line pass against all 21 contract sections
  (explicitly requested to stop discovering gaps one at a time) found
  two 40pt touch targets under the 44pt minimum (fixed), and two
  doctrine-text corrections: the constraint-interpretation engine is
  fully built and live, not the unresolved backend work §17 described
  (marked resolved); the app-wide offline/staleness UI layer genuinely
  doesn't exist yet (added as its own explicit §17 dependency instead of
  building Search-only infrastructure for it ad hoc).

Verification per PR: `npx tsc --noEmit` clean, `npx jest --ci` clean
(46/46 suites, 450/450 tests by the final PR), default `CodeQL` check
verified green specifically (not inferred from the custom `Analyze`
jobs alone) before each merge.

**Scope boundary — do not overclaim from this:** this certification
covers the *Search screen* only. Wave 5's other half, contextual Map
plumbing (`CRAVE_MASTER_CODEX_REMAINING_WORK.md` §3.3), was checked
against the current code as part of this same pass and is **partial**:
direct/city Map mode (`fetch_places_for_map` in
`backend/app/services/query/map_query.py`) still ranks candidates by a
plain bounding-box-scoped `Place.rank_score`, not the shared
recommendation-context contract Feed/Search use — everything else in
§3.3 (exact candidate handoff, no rerank, "Search this area," no
auto-refetch on pan, location-denied fallback, list/map parity, Map
kept contextual not a tab, source attribution) is implemented and
verified. This one item remains open and is not folded into "Wave 5
complete."

**Merged main SHA verified:** `84d8db31a417ca2e8caa32e64cb3b25d85b1b166`
(`git log origin/main`, confirmed directly, not assumed from the PR
merge response alone).

**Railway deployment status: NOT verifiable from this sandbox** — no
Railway dashboard or API access exists in this execution environment.
Only the merged `main` SHA above was verified; whoever has Railway
access should confirm the corresponding deploy separately before
treating this as fully released, not just merged.

## Current real status

- `docs/doctrine/CRAVE_MASTER_CODEX_REMAINING_WORK.md` (new, this update) is
  the consolidated, current, item-by-item checklist of everything left —
  grouped by Migration Plan wave (5 through 10), cross-referenced to the
  Readiness Audit and API/Integration Contracts, with the explicitly-blocked
  OPEN/LATER/AUDIT-REQUIRED list and the permanent Definition-of-Done
  regression gate at the bottom (not itself a wave). Read this before
  claiming any task — it supersedes re-deriving scope from the Migration
  Plan/Readiness Audit separately.
- `CRAVE_CANONICAL_IMPLEMENTATION_INDEX.md` and `CRAVE_CODEX_HANDOFF_STATE.md`
  were updated in the same pass to point to it and to record Waves 3-4 as
  completed baseline.
- Waves 0-4 are merged and must not be redone: Wave 0 (#146 release-defect
  protection), Wave 1 (shared foundations, #170), Wave 2 (visit-evidence +
  Rank ownership, #172), Wave 3 (navigation topology, #185), Wave 4
  (Feed/Decision Session hierarchy).
- Wave 5 Search Screen Contract is merged and certified (PRs #190-#193)
  and must not be redone or reopened without a proven new contract gap.
  Wave 5 contextual-Map plumbing has one open item (§3.3, direct-mode
  ranking source) — pick that up as its own small, scoped fix, not a
  reason to reopen the Search half.
- Two independent tracks may now proceed in parallel: **implementation**
  (Wave 6 — Craves intelligence, `CRAVE_MASTER_CODEX_REMAINING_WORK.md`
  §3.4) and **design** (a Penpot screen-design package, starting with
  Feed/Decision Session, then Search, then Craves, at Exploratory status
  per the locked workflow: define/approve each screen's purpose, layout,
  states, interactions, data, accessibility, and visual rules first,
  then implement without redesigning). Neither blocks the other.
- Four old open PRs, all Claude-authored, none Codex's responsibility,
  all predating current `main` by enough commits to report dirty/unknown
  merge state — need a rebase-or-close decision: #128 (place-issue
  reporting — real, tested backend+migration+frontend feature, looks
  genuinely mergeable after a rebase), #127 (camera-failure-toast +
  dead-control cleanup, likely still valid), #147 (design log Round 2,
  docs-only, likely still valid), #145 (STATE.md housekeeping — now
  fully superseded by this session's own STATE.md rewrites, safe to
  close). Not touched by this update; flagging only.
- The production data-coverage lane (menu/image/Overture canaries,
  scheduler reclaim/video proofs — needs Railway/Supabase access this
  session doesn't have) is bundled in
  `.agent-bridge/claude-to-codex.md`'s current top handoff
  (H-20260907-population-coverage-canaries). This is an **information-
  only inventory, not execution authorization** — an internal audit of
  it (2026-09-07) confirmed the document content is accurate but flagged
  that whoever picks it up must: work from a clean worktree off current
  `origin/main` (not a stale local checkout — one was found 321 commits
  behind with uncommitted changes), re-measure the baseline read-only
  first (every count is a historical 2026-09-02 snapshot), and claim
  exactly one bounded item in this file per `PROTOCOL.md` before running
  anything. Item 6 in that handoff (B1 steps 2/4) additionally needs its
  own scoping pass before it can be claimed at all — it has no cohort,
  command, or rollback plan yet, unlike items 1/2/5. A fuller,
  self-contained execution version of this same plan -- exact commands,
  operating rules, and untried source avenues beyond the six items
  (municipal permit datasets, AllThePlaces, Foursquare gap-fill) -- now
  lives in `docs/CLAUDE_EXECUTION_BRIEF_POPULATION_COVERAGE_2026-09-07.md`,
  written for whichever Claude session (Codex or otherwise) first has
  verified Railway/Supabase/Postgres access.

## Search/Map V1.5 design-audit fixes (Claude, 2026-09-08) — standalone, not a wave claim

User posted the Search/Map V1.5 "Supporting/Edge States" design board (16
edge states SM-05 through SM-16 + 8 resilience/accessibility evidence
cells) and asked for a backend-readiness audit against it. Findings,
each verified against actual code (not the docs):

- **Fixed, merged PR #225** (SHA `b7248f5`): share deep link
  (`crave://place/{id}`) was entirely missing from the native share
  payload despite the design promising one (SM-16). Partial by design —
  works for a recipient who already has CRAVE installed; does nothing
  for anyone else, since no web domain/universal-link infra exists yet
  (confirmed: no `associatedDomains`/`intentFilters`, no CORS web origin
  anywhere in backend config).
- **Fixed, merged PR #226** (SHA `6219346`): `lat`/`lng` only ever
  affected result *ordering*, never exclusion — a "within N miles"
  filter (SM-05/SM-07/SM-14) had nothing enforcing it. Added optional
  `radius_miles` to `GET /search`, filtered via exact haversine cut in
  `execute_search()`, extended constraint-relaxation to cover radius
  (same soft-preference standing as price), cache key bumped v2→v3.
  Backend now fully ready for a radius control; **no frontend UI for it
  exists yet** — a real, not-yet-scoped follow-up if the product wants
  one surfaced.
- **Fixed, merged PR #229** (SHA `df92429`): `hours`/"Closed Place"
  (SM-09) and outdoor-seating (SM-05/06/14) were reported above as
  blocked on missing data — on closer look, they weren't. OSM's
  Overpass fetch (`osm_overpass.py`) has always stored every tag on a
  node verbatim in `discovery_candidates.raw_payload`, including
  `opening_hours` and `outdoor_seating`, at zero extra ingestion cost;
  nothing downstream ever read those two keys. `promote_service_v2.py`
  now turns them into `PlaceClaim`s (OSM source only) through the
  existing claims/truth-resolver pipeline (new `PlaceTruth` rows, zero
  schema change). New `app/services/hours/opening_hours_service.py`
  (via free/open `opening_hours_py`) + `app/services/geo/
  timezone_lookup.py` (free/offline `timezonefinder`, needed because
  OSM's syntax carries no timezone of its own) compute a live open/
  closed/unknown answer — never a guessed or stale status.
  `GET /place/{id}` now returns `hours_status`/`hours_next_change`/
  `hours_raw`/`outdoor_seating`; Place Detail's decision strip renders
  real chips for both. `scripts/backfill_osm_hours_and_seating.py`
  retroactively claims these fields for already-promoted OSM places —
  pure re-read of already-stored `raw_payload`, no re-scrape, idempotent
  — **still needs someone with Railway/Postgres access to actually run
  it once** against production. Ruled out Google Places/Yelp/Foursquare
  deliberately: all need a new account/API key only the user can
  authorize, and Google's ToS additionally forbids long-term caching of
  place data — OSM had neither problem and was already half-wired here.

All four PRs followed the same verification discipline as everything
else in this file: `tsc --noEmit` / `python -m compileall` + `import
app.main` clean, full frontend suite green (48/48 suites, 486/486 tests
by the final PR), full backend suite (1110 passed, 2 skipped by the
final PR) against a **freshly reset** local Postgres schema.

## Next action

Claim the next wave here before starting it — owner, branch, base SHA
(must be current `main` or later), allowed files, and verification plan —
per `.agent-bridge/PROTOCOL.md`. Two independent lanes are open: product
implementation (start from `CRAVE_MASTER_CODEX_REMAINING_WORK.md` §3.4 —
Wave 6, Craves intelligence — or §3.3's one remaining bullet, direct-mode
Map ranking) and production data-coverage (see
`.agent-bridge/claude-to-codex.md`'s current handoff, needs Railway/
Supabase access). The Penpot design track (Feed/Decision Session first)
is a separate workflow, not tracked as a Codex implementation wave claim
here.
This repo moves fast between syncs (Waves 3 and 4 both landed within one
afternoon) — re-check `git log origin/main` before assuming this file is
current.
