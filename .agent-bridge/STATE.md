# Active agent state

Status: doctrine chain complete and certified; implementation Waves 0-4 merged; Wave 5 Search Screen Contract **COMPLETE** and certified (2026-09-07); Wave 5 contextual-Map plumbing **PARTIAL** (one open item, see below); Wave 6 (Craves intelligence) is next and **unclaimed** for implementation; a parallel Penpot design track (Feed/Decision Session, then Search, then Craves) may begin independently at Exploratory status per explicit user direction — design work does not wait on Wave 6 implementation, and Wave 6 does not wait on Penpot.
Owner: none
Branch: main
Head SHA: 84d8db3 (`Merge pull request #193 from Lavish213/claude/wave5-search-contract-audit-fixes`)
Scope: `docs/doctrine/CRAVE_CANONICAL_IMPLEMENTATION_INDEX.md` — **START HERE**; `docs/doctrine/CRAVE_MASTER_CODEX_REMAINING_WORK.md` — **the current operational checklist**, read this before claiming any wave

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
- Two old open PRs (#147 "Round 2 design exploration log", #145
  "agent-bridge final housekeeping") still target a stale base far behind
  current `main` and predate the doctrine merge — need a rebase-or-close
  decision by whoever owns them. Not touched by this update; flagging only.

## Next action

Claim the next wave here before starting it — owner, branch, base SHA
(must be current `main` or later), allowed files, and verification plan —
per `.agent-bridge/PROTOCOL.md`. Start from
`CRAVE_MASTER_CODEX_REMAINING_WORK.md` §3.4 (Wave 6 — Craves
intelligence) for implementation, or §3.3's one remaining bullet
(direct-mode Map ranking) if picking that up instead. The Penpot design
track (Feed/Decision Session first) is a separate workflow, not tracked
as a Codex implementation wave claim here.
This repo moves fast between syncs (Waves 3 and 4 both landed within one
afternoon) — re-check `git log origin/main` before assuming this file is
current.
