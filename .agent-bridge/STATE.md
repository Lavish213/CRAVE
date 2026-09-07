# Active agent state

Status: doctrine chain complete and certified; implementation Waves 0-3 merged; full-app end-to-end check passed clean; Wave 4+ is next and **unclaimed**
Owner: none
Branch: main
Head SHA: 8f9d1da (`feat: Wave 3 navigation topology`, #185)
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
- Full product-doctrine workstream (V1 Scope through the Canonical
  Implementation Index, all PRs #148-#173): **complete, merged to `main`**.
  Do not re-open or redraft any of these without a proven doctrine gap or
  explicit new user direction.
- Implementation **Wave 3 — navigation topology** (PR #185, `feat: Wave 3
  navigation topology`, branch `codex/wave-3-navigation-topology`, closes
  issue #174): merged after this file's previous sync. Bottom tabs are now
  exactly Feed/Search/Craves/Rank/Profile; Map stays at `/map` with
  `href: null` (present in `(tabs)/` for shared layout, removed from tab bar
  — not literally relocated to app-root `Stack.Screen` as the Target Screen
  Registry's exact wording suggested, but achieves the same "not a tab, still
  reachable" outcome; worth a second look if a future contract audit cares
  about the literal file location, not just tab visibility); persistent `+`
  opens `/food-evidence` (a new capture-only screen, intentionally stops
  before publish/log commit — Wave 8 per the PR body owns the full
  composer/evidence write path per `CRAVE_SCREEN_CONTRACT_NATIVE_POSTING.md`);
  Activity is a header-icon route (`/activity`), not a tab. Scope was
  navigation-ownership only per the PR body: no recommendation/evidence
  semantics changed, no legacy routes removed, no unrelated screen redesign.

## Full end-to-end verification (Claude, 2026-09-07, against main @ 8f9d1da)

Ran the actual CI commands locally, not just read the docs:
- Backend: `python -m compileall app` clean; `import app.main` clean;
  `pytest -q` → **1043 passed, 2 skipped**, 0 failures.
- Backend/Postgres invariant: `alembic heads` → exactly one head.
- Frontend: `npx tsc --noEmit` → **0 errors**.
- Frontend: `npx jest --ci` → **45/45 suites, 426/426 tests passed**.
- Repo-wide conflict-marker guard (the same grep CI runs) → clean.
- Manual sweep for TODO/FIXME/"coming soon"/dead controls → the only hits
  (`place/[id].tsx` menu-empty copy, `settings.tsx`'s disabled "Rate CRAVE"
  row) are intentional honest-degraded-state/disabled-control copy per
  doctrine's "missing is missing" rule, not placeholder features silently
  presented as real.
- Cross-checked every YELLOW blocker in `CRAVE_CODEX_READINESS_AUDIT.md` §3
  against its source screen contract and `CRAVE_API_INTEGRATION_CONTRACTS.md`
  — every one is a genuine engineering/data-capability gap (dish
  intelligence pipeline, real taste graph, NLP constraint interpretation,
  etc.) with the product-level shape already locked, not a hidden
  product-decision punt. Two cosmetic issues found, not fixed yet (low
  priority, flagged to the user): some screen contracts still say "deferred
  to the *forthcoming* API/Integration Contract artifact" (that artifact now
  exists); 4 of 15 contracts fold "unresolved dependencies" into
  Traceability's "Forward dependencies" line instead of using the mandatory
  standalone section heading — content is present and correct either way.

**Net result: whole app (both halves) is green end-to-end on the current
main commit.** No regressions found from Wave 3.

## Current real status

- `docs/doctrine/CRAVE_CANONICAL_IMPLEMENTATION_INDEX.md` is the
  authoritative entry point for any implementation work from here forward.
- Waves 0-3 are merged and must not be redone: Wave 0 (#146 release-defect
  protection), Wave 1 (shared foundations, #170), Wave 2 (visit-evidence +
  Rank ownership, #172), Wave 3 (navigation topology, #185).
- Per `CRAVE_CODEX_READINESS_AUDIT.md` §10, the execution order from here is:
  Feed/Decision Session integration → Search → Craves + Contextual Map
  plumbing → Place Detail reconciliation → Native Posting/Private Logging →
  Profile/Taste/Other User Profile → Activity Inbox → Cold Start/remaining
  auth call-site migration/Settings privacy controls → cleanup/legacy-route
  retirement/final V1 QA. The migration plan's own wave numbering is
  authoritative if more specific than this list.
- Two old open PRs (#147 "Round 2 design exploration log", #145
  "agent-bridge final housekeeping") still target a stale base far behind
  current `main` and predate the doctrine merge — need a rebase-or-close
  decision by whoever owns them. Not touched by this update; flagging only.

## Next action

Claim the next wave here before starting it — owner, branch, base SHA (must
be current `main` @ 8f9d1da or later), allowed files, and verification plan
— per `.agent-bridge/PROTOCOL.md`. This repo moves fast between syncs (Wave
3 landed and merged within about 3 hours of this file's previous update) —
re-check `git log origin/main` before assuming this file is current.
