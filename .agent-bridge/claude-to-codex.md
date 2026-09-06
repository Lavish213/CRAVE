# H-20260906-phase4-ranking-transaction-integrity

Status: ready-for-review
Owner: Claude
Branch: claude/phase4-ranking-transaction-integrity (PR to be opened
against main)
Base SHA: 73e5556 (main, post-Phase-3 squash merge -- PR #132)
Commit SHA: 80bc69f
Allowed next files: none from me -- this branch is in review, no more
code planned here unless CI/review findings require it.

## Outcome

Phase 4 of the canonical `CRAVE_PHASES_3_TO_7_PRODUCTION_HARDENING_
EXECUTION_SPEC.md` (Ranking Transaction Integrity), following Phase 3
(Authorization, Identity & Detail Integrity, #132, merged).

Preflight audit read `rank/[placeId].tsx`, `src/api/social.ts`,
`rankings.py`, and `ranking_service.py`. Backend transaction integrity
was already solid -- verified-healthy, left untouched: the comparison-
token flow is stateless between rounds (nothing persists until
convergence, so a duplicate mid-flow submission just wastes a request),
and the *final* round's persistence is already idempotent (unique
constraint + `IntegrityError` catch returning `already_existed: True`,
with event-logging gated on that flag so a replay can't double-log
either). Confirmed exercised by the existing `test_ranking_service.py`
replay test.

Found and fixed three confirmed bugs, all frontend
(`rank/[placeId].tsx`):

1. **Unidentified opponent stayed rankable (P0)** -- matches the
   spec's own flagship example: a failed opponent-detail fetch left
   `opponent` null with no distinguishing flag, so the comparison
   card's "A place you ranked" placeholder still rendered fully
   clickable -- an unidentified place could be submitted as a
   comparison winner. Added `opponentError`, disabled the card
   (`disabled={busy || opponentError || !opponent}`), added a real
   retry that re-fetches just the opponent, and re-checked the same
   condition inside `handleChoose` itself as defense in depth.
2. **Route-generation safety gap** -- `applyStep` never checked the
   existing `placeGenerationRef` before applying its result, so a
   submission still in flight for place A could commit under place B
   after a route change (screen instance reused). Now takes the
   calling handler's captured generation and bails if stale, mirroring
   this screen's own existing guard for its primary place fetch.
3. **No synchronous double-tap guard** -- only the `busy` React state
   guarded re-entrancy, which isn't guaranteed to commit before a
   second fast native touch event's handler runs. Added `submittingRef`
   (mutated synchronously), reset on a genuine placeId change so a
   stale in-flight request for the *previous* place doesn't block the
   *new* place's controls.

## Verification

- Frontend: `npx tsc --noEmit` -> clean. `npx jest` -> 370/370 passed,
  37 suites (367 baseline + 3 new, all in `rank-place.test.tsx`).
- Backend: `python3 -m pytest -q` -> 1041 passed, 2 skipped --
  unchanged from Phase 3's baseline; no backend files touched.

## Known gaps / risks

- Comparison-quality (opponent selection scoping) was reviewed and is
  a deliberate existing design (same-cuisine-category, documented in
  `ranking_service.py`'s own module docstring) -- not rewritten, per
  the spec's own "don't rewrite the recommendation engine
  speculatively" guidance.
- Phases 5-7 (video/media, telemetry/location/async truth, release
  certification) are untouched -- per the spec's strict ordering, each
  is its own later phase on its own fresh branch.

## Next action

Codex: this branch touches only `frontend/app/rank/[placeId].tsx` and
its test file -- no backend changes, so conflicts with your own work
are unlikely unless you're also in that exact file. Once this merges,
Phase 5 (Video/Media Transaction Integrity) is next per the spec, not
yet claimed -- needs its own fresh preflight audit against whatever
`main` looks like at that point, not assumed from this note.
