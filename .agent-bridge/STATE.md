# Active agent state

Status: ready-for-review
Owner: Codex
Branch: codex/foundation-gate-contracts
Base SHA: aef122e
Scope: finish the remaining Foundation Gate contracts: error taxonomy,
React Query conventions, universal-link contract, and privacy/provenance
scopes. No screen redesign, no Place Detail implementation, no production
data work.
Locked files: docs/doctrine/CRAVE_FRONTEND_EXECUTION_ORDER.md,
docs/doctrine/CRAVE_FOUNDATION_GATE_CONTRACTS.md,
frontend/src/contracts/foundationGate.ts,
frontend/src/contracts/foundationGate.test.ts,
.agent-bridge/STATE.md, .agent-bridge/codex-to-claude.md.
Verification: `npx tsc --noEmit --pretty false` passed; targeted Jest passed
with `1 passed, 4 tests` for `src/contracts/foundationGate.test.ts`. Full repo
checkout/full backend suite is blocked locally by host disk space (~115MB
free before cleanup, ~256MB after removing one prunable temp worktree), so
full CI should run on PR.

## FRONTEND EXECUTION ORDER — LOCKED (2026-09-11)

A full frontend audit (verified line-by-line against `main`, not taken on
faith — see that doc's "Grounding findings") plus its remediation strategy
are now locked as the controlling order for all frontend work, superseding
the old wave-numbered sequencing for frontend specifically. Full rationale,
rules, Definition of Done, and grounding evidence live in
`docs/doctrine/CRAVE_FRONTEND_EXECUTION_ORDER.md` — **read that file before
claiming any frontend work below.** This section is the short pointer;
that file is the source of truth for detail.

Locked order:
```
Foundation Gate → Place Detail (proving slice) → Feed/Decision Session
→ Search/Map (propagation-only) → Craves → Rank → Food Evidence/Add Spot
→ Profile/Taste/social cleanup → Auth/Settings/Activity completion
→ cross-app accessibility/E2E/release certification
```

Method: vertical-slice migration, not infrastructure-first. Lock the
minimum shared contracts (Foundation Gate) → prove them on Place Detail →
extract only what's proven → propagate slice by slice, each one shipping a
visibly better screen while migrating the architecture underneath it.
Rejected alternative: 20 infrastructure tasks before touching a screen —
too much invisible-progress risk and speculative-abstraction risk.

**Scope boundary, read before touching Search or Map:** that slice may
propagate shared contracts, reliability, data-state conventions, auth/
error/query ownership, accessibility fixes, and integration hardening
*only*. It must not redesign or reopen the certified Search Screen
Contract or approved Search/Map UX without a new, proven, documented
contract gap — Wave 5 (PRs #190-193) and the V1.5 design-audit fixes (PRs
#225/#226/#229) stay certified.

Locked rules (full text in the doctrine doc): React Query migrates
opportunistically per-route (not a mechanical 30-route pass), with
key/cancellation/stale-time/account-isolation/error-semantics conventions
locked at the Foundation Gate first; `catch {}` occurrences get classified
individually (ignorable-cleanup / recoverable-background / user-actionable
/ invariant), never blanket-banned or blanket-ignored;
`RecommendationEvent` stays fact-only (no fabricated `reason_codes`/
`model_version` ahead of a real ranking model); `crave://` stays as
fallback under a new `https://` universal-link primary; E2E coverage is
built journey-by-journey as each slice lands, not as one final sprint.

**Next action for this lane:** claim **Foundation Gate** in this file
(owner, branch, base SHA, allowed files, verification plan) before writing
any frontend code against this order. Do not start Place Detail before
Foundation Gate's contracts are committed.

### Foundation Gate progress (Claude, 2026-09-11)

Status: **PR #258 merged** (`03bc6cf`, merge commit on `main`). Owner:
Claude. Base at merge time: `main` post-#255/#256/#257 (`40cc186`).

**Real finding:** the `PendingIntent`/auth-gate contract the doctrine
calls for already existed — `authGateStore.ts`'s `AuthResumeEnvelope`
(`actionType`/`reason`/`sourceRoute`/`targetIds`/`payload`/`destination`/
`idempotent`/`expiresAt`/`migrateAnonymous`/`revalidate`/`onInvalid`/
`resume`) plus `AuthGateHost`/`resumePendingAuthAction` is essentially
that contract, already built and already used by Save/Add Spot/posting/
Rank Home. Foundation Gate's actual remaining work here was narrower than
"design a new contract": find and close the screens that don't use the
existing one.

- **Done, PR #258** (branch `claude/foundation-gate-rank-auth-fix`,
  now at `3a71bcd`):
  - `/rank/[placeId].tsx`'s signed-out state was a dead-end static message,
    the first gap of this kind found. Wired into `EmptyState` +
    `requestAuthGate` (`reason: 'rank'`, already a valid enum value),
    matching `rank-home.tsx`'s existing identical pattern exactly.
  - `record-video/[placeId].tsx`'s signed-out state offered a "Go back"
    button and *no sign-in mechanism at all* — worse than a dead end, an
    exit. Now shows a "Sign in" button that opens `AuthSheet` inline
    (`reason: 'default'`, no dedicated copy exists for this action).
  - `place/[id].tsx` had **six separate dead-end sites in one screen** —
    the largest single instance of this bug class found so far: `handleSave`
    (silently no-op'd, not even a toast), `handleAddPhoto`,
    `handleOpenMenuSubmit`, the "Save for tonight" ladder CTA, the "Rank it"
    ladder CTA, "Report the main photo", and "Report an issue" all either
    toasted "Sign in to..." with no way to act on it, or (handleSave) gave
    no feedback whatsoever. All seven call sites now route through a new
    local `gateSignIn` helper wrapping `requestAuthGate`
    (`save`/`rank`/`default` reasons as appropriate; the Rank CTA carries
    `destination: /rank/{id}` back to itself).
  - All three fixes use `resume: () => undefined` (deliberate no-op) —
    matches the established safe pattern: a `resume` closure captured at
    gate-request time would close over that render's `user` (null),
    so auto-resuming the mutation later would run on stale state.
    Component-level `useAuthStore` subscriptions re-render the caller past
    the signed-out branch instead; the user re-taps.
  - Verification: `tsc --noEmit` clean (0 `error TS` across the whole
    project), `place-detail.test.tsx` 35/35 (new signed-out-gate suite
    added), `record-video.test.tsx` 15/15 (new sign-in test added).
    CI green (7/7 real checks: Guard, Frontend, Backend x2, Analyze x2,
    CodeQL), CodeRabbit skipped per repo policy (<10 stars, OSS), no open
    review threads. Merged to `main` at `03bc6cf`.
- **Auth-gate sweep completed this pass** (grepped every screen in
  `frontend/app` for `if (!user)` and `Sign in to`, not just the three
  screens already named above): Craves, Search/Map, Feed
  (`(tabs)/index.tsx`), rank-home, add-spot, food-evidence, Profile, and
  Leaderboard all already gate correctly via `AuthSheet`/`requestAuthGate`
  — verified by reading each site, not assumed. `add-spot.tsx`'s
  `handleConfirm` still has a bare `toast('Sign in to add a new spot')`
  guard, but it's dead code in practice: the whole screen returns an
  `AuthSheet`-gated empty state at the `state === 'unauthenticated'`
  branch before that handler is ever reachable — left as-is, not a real
  gap.
  - **Found and fixed, same PR**: `friends-feed.tsx` had no signed-out
    branch at all — its account-scoped query is simply `enabled: !!user`,
    so signed out it fell through to the generic "Nothing here yet /
    Follow people to see..." empty state, identical to what a genuinely
    friendless signed-in user sees, with a "Find people" CTA that never
    mentioned signing in. Now shows its own "Sign in to see friend
    activity" gate first, same `EmptyState` + `AuthSheet` pattern as the
    others. Test added (9/9 passing), `tsc --noEmit` clean.
  - Also checked: Activity (`activity.tsx`) is a static "coming soon"
    placeholder with no data fetching and nothing to gate; Settings
    (`settings.tsx`) simply hides its ACCOUNT/DANGER ZONE sections when
    signed out (`user ? ... : null`) rather than attempting and blocking
    an action — neither is this bug class. No dedicated Taste Profile
    route exists separately from `(tabs)/profile.tsx`, already covered
    above. This closes out the sweep: every screen in `frontend/app` has
    now been individually checked for this specific gap, not sampled.
- **Still not started**: error taxonomy (offline/timeout/unauthorized/
  forbidden/not_found/rate_limited/server_error/invalid_data/unknown +
  UX mapping), React Query key/cancellation/stale-time/account-isolation
  conventions (only 4 of ~30 routes use RQ at all today), the
  `https://` universal-link contract (still `crave://`-only), and the
  privacy/provenance scopes (private/shareable/display-identity/
  explicit-opt-in; value/source/fetched_at/confidence for place data).
  None of these were touched this pass — don't claim Foundation Gate
  complete from the Rank fix alone.

## Other active lanes (independent, not blocked by the above)

### OSM backfill production run

Status update, 2026-09-11: the duplicate-claim dedupe fix is **merged**
(PR #243, SHA `a271856` on `main`) — confirmed directly by reading the
merged `backend/scripts/backfill_osm_hours_and_seating.py` (the
`scheduled_claim_keys` in-memory set is present). The original crash this
fixed: a first real production attempt reached
`scanned=2500 claims_written=30 places_affected=27` then hit
`psycopg2.errors.UniqueViolation` on a duplicate deterministic claim
within one run; those 30 claims stayed committed, the failing batch
rolled back.

Codex has since relayed (2026-09-11, **not yet independently verified by
this session** — no Railway/Postgres access here) that a fresh dry-run on
the merged fix reproduced the original dry-run numbers exactly
(`osm_candidates_scanned=11239`, `claims_written=4289` from
`candidates_touched=3634`, `places_affected=3631`), then a real apply was
started and was actively progressing batch-by-batch with no errors as of
that report. **Do not treat this as complete** until: (a) the run reports
a final done state with no crash, (b) an idempotent dry-run rerun
afterward reports `claims_written=0`, and (c) a real `GET /place/{id}`
spot-check on a known OSM place shows non-null `hours_status`/
`outdoor_seating`. Whoever confirms all three should record the exact
numbers and the spot-checked place id here, replacing this paragraph.

### Menu backlog canary status

Still not run. Verified blocker, unchanged: current
`backend/scripts/run_menu_backlog_canary.py` requires exact `--place-ids` or
`--place-ids-file`; a bare `--run --confirm-count 10` is insufficient, and
no reviewed 10-place cohort has been recorded anywhere durable yet.

Next action: once production DB access is available, build/record a
reviewed 10-place ID file, preview it, then run with
`--place-ids-file <reviewed-file> --run --confirm-count 10` and review all
outcomes immediately.

### Menu item source provenance — PR #252

Codex's own PR (`codex/menu-provenance-fix`, not this session's), fixing
menu-item source lineage through canonicalization/claim emission and
refusing anonymous claims with no source URL. CI green (8/8, including the
previously-slow real-Postgres suite), CodeRabbit review requested.
Explicitly holds off any new production menu-publish canary run until
after merge + fresh authorization — correct posture, matches this file's
own standing rule for canaries. Not this session's PR to merge; watch for
its outcome, don't act on it uninvited.

### Posting V2 composer stack (Codex, in progress — not yet merged)

Building directly on this session's merged Posting V2-A (PR #244 backend
SHA `e361e1b`, PR #245 frontend SHA `8d3023d`, both on `main`): seven PRs
since 2026-09-09, none merged yet, all still draft —
`#246` (fixes a real race left in the merged #245 draft store: candidate
selection left `outcome='pending'`, letting a rapid existing-place tap
steal the same draft's media — adds an `awaiting_place` outcome to close
it), `#247` (doctrine freeze: `CRAVE_POSTING_MEDIA_V2_ARCHITECTURE.md`,
a Posting screen contract, a backend contract — docs only), `#248`
(composer state fields: intent/reaction/caption/visibility/occurredAt,
persisted-store migration), `#249` (new `FoodContribution` model +
`/api/v1/contributions` API — additive, isolated, own migration, CI
green), `#250`/`#251` (unified composer frontend: `/posting-restaurant` +
rewritten `food-evidence.tsx` composer, replacing the #245
attach-immediately bridge), `#253` (the consolidated end-to-end version of
the whole stack, backend + frontend together, directly against `main`).

This session reviewed the stack (diffs read, not just descriptions) and
found #246/#248/#249 correctly implemented and tested. #253 had a real,
reproducible CI failure — `tsc` errors from stale `DraftOutcome` literals
in `add-spot.test.tsx` plus a type mismatch in `friends-feed.tsx` — that
had silently persisted across #250 and #253 (18+ hours, two PR iterations)
because `tsc` failing meant the Jest step never even ran in CI. Fixed
directly on `chatgpt/posting-v2-composer` (commit `846a3b1`): corrected
the two stale literals, the `friends-feed.tsx` type mismatch, and fully
rewrote both `add-spot.test.tsx` and `food-evidence.test.tsx` (which were
still asserting entirely stale pre-composer copy/behavior — fixing the
types alone would only have moved the failure to Jest). Verified: `tsc
--noEmit` clean, full frontend suite green (50/50 suites, 533/533 tests),
backend untouched and clean, and confirmed green in real CI afterward
(8/8 checks on PR #253, including Frontend typecheck+tests). Not this
session's PR stack to merge — it's Codex's active, still-evolving branch;
this was a narrow CI-unblock, not a claim on the work.

## Previous compacted context

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

## App-wide screen audit (Claude, 2026-09-09) — standalone, not a wave claim

User asked for a full screen-by-screen audit of every route in
`frontend/app` (not just Search), same rigor as the Search subsystem
audit below: full file reads, API-contract cross-checks against backend
routes, dead-code/gap/broken-control checks, race-condition review.

- Confirmed **fixed** (no longer gaps) from the earlier
  `SCREEN_INVENTORY_UX_DESIGN_AUDIT_2026-09-06.md`: Rank's retry buttons
  are genuine refetches, record-video's failed `recordAsync()` now
  toasts a real error, Leaderboard has a distinct Friends sign-in gate,
  Craves' remove-a-save now confirms via `Alert.alert`.
- Confirmed a real cross-screen bug class (client-side filtering
  against a capped/paginated fetch) present in Search, Feed, and Map —
  already fixed with three screen-specific patches, merged PR #234
  (SHA `c8abbc5`). Confirmed **absent** elsewhere (`rank-home.tsx`'s
  `list_user_rankings()` is a genuine unbounded fetch).
- Full remaining sweep (rank-home, rank/[placeId], friends-feed,
  add-spot, settings, record-video, user/[id], taste-profile, activity,
  legal, profile-setup, +not-found, both root layouts): no new gaps
  except two, both below.
- **Fixed, merged PR #236**: `taste-profile/[userId].tsx` collapsed any
  non-404 error on `fetchProfile`/`fetchTasteProfile` into the same
  false "not found"/"no taste profile yet" states as a genuine 404 or
  empty profile, with no retry — same anti-pattern its sibling
  `user/[id].tsx` already fixed via `profileError`. Added the matching
  `profileError`/`tasteError` states here too.
- **Fixed, merged PR #238** (SHA `746b6e1`): the "+" FAB's
  `food-evidence.tsx` captured a photo/video, then "Continue" dropped it
  entirely — no upload call, no param passed to `add-spot.tsx`, no
  queue. Implemented option A from
  `.agent-bridge/claude-to-codex.md`'s `H-20260909-food-evidence-media-
  drop` handoff (now resolved/compacted there): `food-evidence.tsx`
  carries `{ uri, kind, fileSize, mimeType }` as route params;
  `add-spot.tsx` wires the actual upload only when a `place_id` already
  exists (`already_in_crave: true` — photo via the existing
  `useUploadImage()` flow, video via the existing
  `videoQueueStore.recordVideo()`); the new-candidate branch
  (`confirmNewSpot()` only ever returns a `candidate_id`, never a
  `place_id`) now says so explicitly instead of pretending it uploaded.
  CodeRabbit caught a real double-attach race on rapid "Open" taps
  (`mediaOutcome` state read before its own setter's render committed);
  fixed with a synchronous `mediaClaimedRef` guard, same pattern as
  `rank/[placeId].tsx`'s `submittingRef`. **Known accepted gap**: the
  new-candidate branch still can't attach media at confirm time —
  that's option B from the handoff (backend support for pending media
  on `DiscoveryCandidate`), not implemented, not silently dropped either
  (the toast says so).

## Next action

Superseded by the top of this file — **frontend work now follows
`docs/doctrine/CRAVE_FRONTEND_EXECUTION_ORDER.md`** (Foundation Gate next),
not the wave numbering this paragraph used to point to (Waves 0-7 are
merged baseline, done, not reopened). Independent lanes still open:
production data-coverage (OSM backfill apply in progress per Codex's
relay, unverified here — see "Other active lanes" above; menu
canary/population-coverage still need Railway/Supabase access — see
`.agent-bridge/claude-to-codex.md`'s current handoff), and the Posting V2
composer stack (Codex's, in progress, see above). The Penpot design track
(Feed/Decision Session first) is a separate workflow.

Claim any task here before starting it — owner, branch, base SHA (must be
current `main` or later), allowed files, and verification plan — per
`.agent-bridge/PROTOCOL.md`. This repo moves fast between syncs — re-check
`git log origin/main` before assuming this file is current.
