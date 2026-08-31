# Active agent state

Status: reviewed-and-merged
Owner: Claude
Branch: main
Base SHA: (post-merge of PR #95, "Gate standalone scheduler rollout")
Scope: Reviewed and merged Codex's PR #95 -- a default-off standalone
scheduler-worker rollout gate plus explicit job allowlist, so a Railway
worker service can be provisioned without immediately executing every
accumulated production backlog. Embedded/local scheduler behavior is
unchanged (verified directly at `main.py`'s zero-arg `create_scheduler()`
call site, not just via tests). Production provisioning is still not
authorized by this merge alone -- see Next action.
Verification performed by Claude before merging: reran the 6 new focused
tests plus the full backend suite locally (939 passed, 2 skipped, matches
PR body exactly); independently deleted the default-off guard and
confirmed the most safety-critical test fails as expected, then restored
it; traced the embedded-scheduler call site by hand; confirmed
`git diff --check` clean; confirmed all 8 CI checks green. Full writeup
posted as a review comment on PR #95.
Known gaps: no Railway scheduler-worker service exists yet, no production
job is enabled. This PR only removes the code-side blocker.
Next action: Codex, when back: (1) provision the standalone worker service
on Railway with `SCHEDULER_WORKER_ENABLED=false` per
`docs/SCHEDULER_WORKER_ROLLOUT.md`, verify the disabled log line, (2) once
stable, enable jobs one at a time per that doc's phased plan starting with
`moderation_queue_health_check`, (3) for menu_enrichment specifically, use
`scripts/run_menu_backlog_canary.py` (PR #93) for the first bounded run --
preview first, then `--run` with an exact `--confirm-count`, not the
scheduler job. Nothing here needs any further code change from either of
us before that infra step.

## Prior Claude pass (E8 audit + PR #93 canary)

A large end-to-end audit pass per the user's request to "search project
end to end for all gaps and bugs... check everything... pretend to be
user... fix or log" -- covering a user walkthrough (incl. camera/upload),
a full schema audit, an accessibility re-verification, and 2 design/
tradeoff docs (E8 taxonomy, E2/E3/E10) -- plus, in response to Codex's
production-topology finding (no scheduler-worker service deployed in
Railway, and the existing A1 tooling being unsafe for a first canary
run), the exact-target, confirmation-gated menu-extraction canary tool
(PR #93) referenced above.

## The scheduler-worker finding (Codex's, confirmed by me at the code level)

Codex found via direct Railway inspection: only a `CRAVE` web service +
Postgres exist, no scheduler-worker service, `RUN_EMBEDDED_SCHEDULER=false`
on the web service. I traced this in the code and it's fully consistent:
`app/main.py`'s lifespan correctly skips starting the scheduler when that
flag is false, and `app/scheduler_worker.py` (a complete, production-
ready standalone process -- proper SIGTERM handling, Sentry init, clean
shutdown) is exactly the replacement service that flag expects to exist
elsewhere. It just isn't deployed. This means every scheduled job --
menu enrichment, image ingestion, video processing, score recompute, my
own PR #88 stuck-photo-recovery job -- is currently running nowhere in
production, regardless of what the code says it should do.

This directly supersedes an earlier "false alarm, scheduler verified
running in a separate Railway project, do not touch" resolution from
earlier in this session's master plan -- that earlier finding should be
treated as stale/wrong now, not Codex's fresh, specific inspection.

One correction to Codex's own framing: `scheduler_worker.py` doesn't
need to be built -- it already exists, complete. The actual gap is purely
deploying it as its own Railway service. That's infrastructure work
outside what either of us can do without Railway/production access.

## What I built (PR #93): the exact-target A1 canary

Codex separately flagged the existing A1 tooling (the scheduler job +
`scripts/run_menu_worker.py`) as unsafe for a first backlog run: it
selects places itself (highest rank_score first), no preview, no way to
confirm you ran against exactly N intended places.

`backend/scripts/run_menu_backlog_canary.py` (new): takes an explicit
place-ID list only, never a discovered/ranked selection. Preview-by-
default; `--run --confirm-count N` (must exactly match) to execute --
same discipline as the existing Overture population canary. Refuses on
any missing/inactive place ID. Capped at 100 places/run. Does NOT attempt
automated rollback of a materialized menu (explained in the script's own
docstring why that's harder than the Overture canary's case) -- but
every result row names exactly which place_ids were touched, for a
reviewable manual rollback if one's ever needed.

Refactored menu_worker.py's per-place logic into a shared
`_process_one_place()` method (pure, behavior-preserving refactor -- all
13 pre-existing tests pass unchanged) so the canary and the batch worker
call identical, already-tested code instead of risking drift.

## Current state of the Master Plan

- A1: the exact-target tool now exists (PR #93). Running it against real
  place IDs, and deploying the scheduler-worker service, are both still
  blocked on production access.
- A3: diagnosis complete (PR #85, merged and deployed, confirmed at SHA
  95d9063). Both sources remain correctly unpublished.
- A7, B1 steps 2/4: unchanged, still need production access.

Locked files: none currently held.
Verification plan: full suite green on every change (933 backend passed,
2 skipped as of this pass); every new/changed test independently
verified to catch its corresponding regression before merge.
Next action: Codex, when back: (1) provision the scheduler-worker
Railway service (code is ready, this is pure infra), (2) once that's
live and observed stable, use scripts/run_menu_backlog_canary.py for a
small, reviewed A1 canary batch -- preview first, then --run with an
exact --confirm-count, (3) B1 steps 2/4 whenever convenient.

## Existing local work excluded from this bridge

`eas.json`, `package.json`, `frontend/package-lock.json`, `.agents/`, and
`docs/CRAVE_MASTER_EXECUTION_ROADMAP.md` were already dirty when this
bridge was created. They are not owned by this task.
