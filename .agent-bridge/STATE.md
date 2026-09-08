# Active agent state

Status: doctrine chain complete and certified; implementation Waves 0-4 merged; Wave 5 Search Screen Contract **COMPLETE** and certified (2026-09-07); Wave 5 contextual-Map plumbing **PARTIAL** (one open item, see below); **Wave 6 (Craves intelligence) COMPLETE** (all 4 steps merged, 2026-09-08); **Wave 7 (Place Detail relationship hierarchy) is claimed and in progress** (Claude, this session) against `docs/doctrine/CRAVE_SCREEN_CONTRACT_PLACE_DETAIL.md`; a parallel Penpot design track (Feed/Decision Session, then Search, then Craves) may begin independently at Exploratory status per explicit user direction — design work does not wait on implementation waves, and vice versa.
Owner: Claude
Branch: main (Wave 7 sub-PR 1 not yet branched)
Head SHA: 9056b80 (`Merge pull request #219` — current `origin/main`)
Scope: `docs/doctrine/CRAVE_CANONICAL_IMPLEMENTATION_INDEX.md` — **START HERE**; `docs/doctrine/CRAVE_MASTER_CODEX_REMAINING_WORK.md` — **the current operational checklist**, read this before claiming any wave; `docs/CLAUDE_EXECUTION_BRIEF_WAVES_7_10_2026-09-08.md` — self-contained Waves 7-10 brief with concrete buildable-now-vs-blocked findings already verified against current code, for any Claude session resuming this work

## Wave 6 — Craves intelligence — COMPLETE

All 4 steps merged: (1) backend + typed client, PR #215; (2) screen
rebuild around the reasoned subset, PR #216; (3) automatic cuisine/
geography clustering, PR #218; (4) doctrine correction reclassifying
contract §11 as blocked on §3.6 (operational-data ingestion, app-wide,
not Craves-specific), PR #219. Contract status: **GREEN**. One tracked,
non-blocking gap remains: the "Craves"/"Added" sections still render via
their own bespoke row style, not `PlaceCardCompact`, pending `/craves`
and `/hitlist/me` returning full `PlaceOut` instead of bare IDs.

## Wave 7 — Place Detail relationship hierarchy, in progress (Claude)

Per `docs/doctrine/CRAVE_MASTER_CODEX_REMAINING_WORK.md` §3.5 and
`docs/doctrine/CRAVE_SCREEN_CONTRACT_PLACE_DETAIL.md` (Draft, pending
audit). Scoping research (read screen contract in full, old spec,
current `app/place/[id].tsx` 1196 lines, VisitEvidence/HitlistSave/
PlaceRanking models, nav call sites from craves/search/feed) found:

**Buildable now, this session, no production access needed:**
- Stop persuading after a confirmed visit -- `HitlistSave.visited`/
  `VisitEvidence` already exist, just needs the conditional wired in.
- Reuse the shared `DecisionStrip` component -- exists, used elsewhere
  (Craves, Search, `PlaceCardCompact`), but Place Detail hand-rolls its
  own `decisionStrip`/`whyFits` views instead of using it (lines 482-570).
- Adaptive primary CTA ladder, minus Reserve (see blocked, below).
- "Considering tonight" / "visited-not-regular" relationship detection
  -- buildable from existing HitlistSave/VisitEvidence, needs wiring.
- Remember why an unvisited place was saved/recommended -- genuinely
  buildable (not blocked): needs a new nullable `reason_role`/
  `reason_source` column on `HitlistSave` populated optionally at
  save-creation time, since no such field or nav-param threading exists
  today (`craves.tsx`/`SearchScreen.tsx`/`MapScreenCore.tsx` all call
  bare `router.push('/place/${id}')`, discarding `decision_role`/
  `craveRole`/`searchReason` at the point of navigation).
- "Regular" tier: no visit-count/frequency field exists anywhere
  (`VisitEvidence` dedups by `source_ref=save.id`, so repeated "I ate
  here" toggles never create more than one row; `PlaceRanking` has a
  unique `(user_id, place_id)` constraint, no revisit counter). A real,
  additive counter (increment only on `visited` False→True transition)
  is buildable now -- not fabricating a signal, adding a real one.
- Correction action: photo/place reporting already fully built and
  wired (`ReportPhotoSheet`, `ReportPlaceSheet` → `moderation.py`).
- Preserving existing integrations through the refactor (guard refs,
  moderation logic) -- care during the rebuild, not new work.

**Genuinely blocked, not attempted:**
- Reserve as a CTA rung -- no reservation-provider integration exists
  anywhere in the app (OpenTable/Resy/etc.); this is a real external
  integration dependency, not a data-modeling gap.
- Why-This-Fits' 4-action taste-correction vocabulary (Not true /
  Doesn't matter / Less / More) -- needs the Gate 2 taste graph
  (`CRAVE_MASTER_CODEX_REMAINING_WORK.md` §3.8), which does not exist.
  Contract §22/§12 already name this as an unresolved dependency.
- Dish Intelligence-dependent menu personalization, real operational
  open/closed status, media provenance (§3.6-3.10) -- pre-existing,
  named blockers on Place Detail's overall contract status (YELLOW),
  not Wave 7-specific and not attempted here.

**Plan:**
1. Backend groundwork: `visit_evidence_for_place()` helper,
   `reason_role`/`reason_source` columns on `HitlistSave`, a real
   revisit counter -- one PR, migration verified against local Postgres.
2. Frontend: rebuild Place Detail's top-of-page around the four
   relationship modes, swap in shared `DecisionStrip`, adaptive CTA
   ladder, thread reason through navigation from craves/search/feed --
   one PR, building on (1).
3. Doctrine status update documenting the blocked items above precisely
   (same treatment as the Search §17 and Craves §11 corrections), not
   silently claiming Wave 7 "done" when Reserve and the taste-correction
   vocabulary are real, out-of-reach dependencies.

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
