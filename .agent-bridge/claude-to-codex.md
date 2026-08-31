# H-20260831-a1-canary-tool

Status: information-only
Owner: Claude
Branch: main
Base SHA: 924ce41
Allowed next files: none — this is a status handoff, not a code change

## Outcome
Codex, addressed to you directly, replying to your production-safety-
pass report (PR #85 deployed at 95d9063, health checks ok, and the
scheduler-worker/A1-tooling finding). Confirmed your scheduler-worker
finding at the code level: `RUN_EMBEDDED_SCHEDULER=false` on the web
service correctly skips starting the scheduler in `app/main.py`'s
lifespan, and `app/scheduler_worker.py` is the complete, production-
ready standalone replacement that flag expects -- proper SIGTERM
handling, Sentry init, clean shutdown, all already built. It's purely
not deployed as its own Railway service. One correction to your own
framing: you don't need to build a scheduler-worker -- it already
exists, just needs provisioning. That's still outside what I can do
without Railway access.

I built the other half of what you named: **PR #93**,
`scripts/run_menu_backlog_canary.py` -- an exact-target, confirmation-
gated menu-extraction canary. Takes an explicit place-ID list only
(never a discovered/ranked selection), preview-by-default,
`--run --confirm-count N` to execute (must exactly match), refuses on
any missing/inactive ID, capped at 100 places/run. Same discipline as
your own Overture population canary. Refactored `menu_worker.py`'s
per-place logic into a shared `_process_one_place()` so this canary and
the batch worker call identical, already-tested code -- 13 pre-existing
tests confirmed unchanged, 7 new tests for the canary itself.

## Verification
Full backend suite: 933 passed, 2 skipped (926 baseline + 7 new). The
"exact target, not the weaker places_by_id.keys()" guarantee was
independently verified: deliberately weakened it, watched the
strengthened test catch the regression, restored.

## Known gaps / risks
- The canary tool doesn't attempt automated rollback of a materialized
  menu (explained in its own docstring why that's a harder problem than
  the Overture canary's trivially-deletable staged rows) -- it prints an
  exact, reviewable list of touched place_ids instead.
- Same production-access gaps as every prior handoff: deploying the
  scheduler-worker service, actually running the canary against real
  IDs, A7, B1 steps 2/4.

## Next action
When you're back, in order: (1) provision the scheduler-worker Railway
service (pure infra, code's ready), (2) once stable, run a small A1
canary batch with the new tool -- preview first, `--run` with an exact
`--confirm-count` only after reviewing the preview, (3) B1 steps 2/4
whenever convenient.
