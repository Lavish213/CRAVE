# Active agent state

Status: ready-for-review
Owner: Claude
Branch: claude/phase4-ranking-transaction-integrity (PR to be opened
against main)
Base SHA: 73e5556 (main, post-Phase-3 squash merge -- PR #132)
Commit SHA: 80bc69f
Scope: Phase 4 of the canonical CRAVE_PHASES_3_TO_7_PRODUCTION_HARDENING_
EXECUTION_SPEC.md -- Ranking Transaction Integrity.
Locked files: none -- handoff complete.

## Outcome

Preflight audit read `frontend/app/rank/[placeId].tsx`, the ranking API
wrapper (`src/api/social.ts`), the backend ranking route
(`rankings.py`) and service (`ranking_service.py`), and the existing
service-level idempotency tests (`test_ranking_service.py`). Backend
transaction integrity was already solid -- verified-healthy, left
untouched:

- The comparison-token flow (`start_ranking`/`submit_comparison`) is
  stateless between rounds (a signed, short-lived JWT carrying binary-
  search bounds), so a duplicate submission for a *non-final* round just
  wastes a request, nothing persists until convergence.
- The *final* round's persistence is already guarded by
  `PlaceRanking`'s unique constraint + an `IntegrityError` catch that
  returns the existing ranking as `already_existed: True` rather than
  raising -- confirmed exercised by `test_ranking_service.py`'s existing
  replay test.
- The route only logs the Recommendation Ledger `rank` event and marks
  an existing save visited when `not already_existed` -- a replayed
  final submission can't double-log either.

Found and fixed three confirmed frontend bugs, all in
`rank/[placeId].tsx`:

- **P0 -- unidentified opponent stayed rankable** (confirmed, matches
  the spec's own flagship example almost verbatim): when the
  opponent's own detail fetch failed, `opponent` was simply left
  `null` with no distinguishing flag. The comparing-stage card still
  rendered its "A place you ranked" placeholder fully clickable via
  `ComparisonChoice`'s `onChoose` -- an unidentified place could still
  be submitted as the winner of a real comparison. Added a distinct
  `opponentError` state: the card now shows "Couldn't load"/
  "Unavailable" and is disabled (`disabled={busy || opponentError ||
  !opponent}`), with a real retry that re-fetches just the opponent
  (`handleRetryOpponent`, using a new `opponentPlaceIdRef` since the
  fetch failure means the resolved place itself was never available to
  retry from). `handleChoose` itself also re-checks the same condition
  before calling `submitComparison('opponent', ...)`, so nothing (a
  stale closure, a timing quirk) can route around the disabled card.
  "Can't decide" and the just-ranked place's own card (always valid --
  gated by the existing `place.id !== placeId` check) remain available
  either way.
- **Route-generation safety gap** -- `applyStep` (shared by both
  `startRanking`'s and `submitComparison`'s response handling) never
  checked `placeGenerationRef` before applying its result. A submission
  still in flight for place A that resolved after the user had already
  navigated to rank place B (screen instance reused, matching this
  screen's own existing `placeId`-change guard for the primary place
  fetch) could commit A's ranking result under B's now-current route.
  `applyStep` now takes the calling handler's captured generation and
  bails if it no longer matches `placeGenerationRef.current`, mirroring
  the exact pattern this screen already used for the place-detail
  fetch itself.
- **No synchronous double-tap guard** -- `handlePickTier`/
  `handleChoose` only ever guarded re-entrancy via the `busy` React
  state. State updates aren't synchronous or guaranteed to commit
  before a second rapid native touch event's handler runs, so two fast
  taps could both pass the `!busy` check before either's `setBusy(true)`
  took effect -- backend transaction integrity already prevents this
  from double-persisting a *final* ranking, but it would still fire a
  wasted duplicate request and (for a non-final round) inflate the
  visible `round` counter by one per extra tap. Added `submittingRef`
  (a ref, mutated synchronously) alongside `busy`, checked in both
  handlers; reset on a genuine placeId change too, so a submission
  still in flight for the *previous* place doesn't go on blocking the
  *new* place's own controls until that stale request happens to
  settle.

## Verification

- Frontend: `npx tsc --noEmit` clean. `npx jest` 370/370 passed, 37
  suites (367 baseline + 3 new, all in `rank-place.test.tsx`).
- Backend: `python3 -m pytest -q` 1041 passed, 2 skipped -- unchanged
  from Phase 3's baseline; no backend files touched this phase.

## Known gaps / risks

- Comparison-quality auditing (opponent selection, e.g. destructively
  mismatched cuisine/price/repeated-opponent burden) was reviewed
  against the spec's own "do not rewrite the recommendation engine
  speculatively" guidance -- the existing same-cuisine-category scoping
  is a deliberate, already-documented design choice (see
  `ranking_service.py`'s own module docstring), not a bug. Left
  untouched.
- The event-semantics requirement ("rank is a strong preference event,
  analytics failure must not undo a successfully persisted ranking")
  was verified already correct on the backend (`record_ranked_place`/
  `record_rank_outcome` run in the same request after `db.commit()` of
  the ranking itself, and are keyed off `already_existed` for dedup) --
  no client-side ranking-specific analytics call exists to audit
  separately.
- Phases 5-7 (video/media transaction integrity, telemetry/location/
  async truth, performance/accessibility/security/release
  certification) are untouched -- per the spec's strict ordering, each
  is its own later phase on its own fresh branch.

## Next action

Push this branch, open a narrow PR against main following the spec's
required PR contract, request CodeRabbit review, hold to the same
three gates Phases 1-3 used (CI green including the real-Postgres job
-- though this phase touches no backend files, so it should be a pure
formality here -- review threads resolved, no scope creep) before
merge. After merge, Phase 5 (Video/Media Transaction Integrity) is
next per the spec's strict ordering -- not yet claimed, needs its own
fresh preflight audit against whatever `main` looks like at that
point.
