# Active agent state

Status: doctrine chain complete and certified; implementation Waves 0-2 merged; Wave 3 (navigation topology) is next and **unclaimed**
Owner: none
Branch: main
Head SHA: 57e7588 (`docs: certify CRAVE Codex-ready baseline`, #173)
Scope: `docs/doctrine/CRAVE_CANONICAL_IMPLEMENTATION_INDEX.md` — **START HERE**, this file is now a pointer to it, not a duplicate of its content

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
- Full product-doctrine workstream (V1 Scope, Target Screen Registry, Route
  & Flow Map, Data & State Map, Privacy/Permission Matrix, Evidence/Signal
  Hierarchy, Design System, Component Registry, all 15 screen contracts,
  API/Integration Contracts, Requirements Traceability Matrix, Implementation
  Migration Plan, Codex Implementation Rules v2, Codex Readiness Audit,
  Codex Handoff State, Canonical Implementation Index): **complete, merged
  to `main`**. Every one of PRs #148-#173 landed. Do not re-open or redraft
  any of these without a proven doctrine gap or explicit new user direction.

## Current real status (verified against `main` @ 57e7588, 2026-09-07)

- `docs/doctrine/CRAVE_CANONICAL_IMPLEMENTATION_INDEX.md` is the authoritative
  entry point for any implementation work from here forward. Read it first.
- Implementation Wave 0 (protected #146 release-defect fixes) and Wave 1
  (shared foundations — typography roles, Decision Strip, resumable auth
  gate, recommendation-context/privacy/evidence primitives — PR #170) and
  Wave 2 (visit-evidence persistence, Rank queue, Rank Home ownership,
  Profile handoff — PR #172) are merged. Details and hard invariants are in
  `docs/doctrine/CRAVE_CODEX_HANDOFF_STATE.md` — do not redo these waves.
- **Wave 3 — navigation topology** (exactly five tabs: Feed/Search/Craves/
  Rank/Profile; Map as a contextual route, not a tab; persistent `+` action;
  Activity as a header/inbox destination, not a tab; preserve deep links and
  auth-return destinations) is the next executable unit per
  `CRAVE_IMPLEMENTATION_MIGRATION_PLAN.md`. No branch or open PR currently
  targets it (checked `list_pull_requests`/`branch -r` 2026-09-07 — none
  found beyond old unrelated open PRs #147, #145, #128, #127, #126, #49 and
  dependabot bumps, none of which touch navigation topology).
- Two old open PRs (#147 "Round 2 design exploration log", #145 "agent-bridge
  final housekeeping") both target a stale base far behind current `main`
  and predate the entire doctrine merge — likely need a rebase-or-close
  decision by whoever owns them before they're actionable again. Not touched
  by this update; flagging only.

## Next action

Claim Wave 3 (navigation topology) here before starting it — owner, branch,
base SHA (must be current `main` @ 57e7588 or later), allowed files, and
verification plan — per `.agent-bridge/PROTOCOL.md`. Read
`CRAVE_CANONICAL_IMPLEMENTATION_INDEX.md` §3-4 and
`CRAVE_CODEX_HANDOFF_STATE.md`'s Wave 3 target list first; do not redesign
Feed/Search/Craves/Profile screen content as part of navigation-only work,
and do not reintroduce full Rank ownership into Profile or make Map
independently rerank a source screen's candidate set.
