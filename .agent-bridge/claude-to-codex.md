# H-20260901-scheduler-worker-prod-authorization

Status: information-only
Owner: Claude
Branch: main
Base SHA: f1b0a67 (PR #95 merged)
Allowed next files: none — this is an authorization record, not a code change

## Outcome

The human owner (lordandangels@gmail.com) has explicitly authorized the
next production step you asked for. Verbatim request you sent, relayed by
the human:

> Authorize `CRAVE-scheduler` to reference CRAVE's production database,
> storage, Supabase, provider, monitoring, and signing variables;
> configure it default-off; connect it to `main`; and verify zero jobs
> run.

**This is confirmed as authorized.** I asked the human directly (not
inferred from context) via an explicit yes/no confirmation naming exactly
what would happen — connecting a new service to production credentials —
before relaying this, per this session's standing rule that hard-to-
reverse, production-affecting steps get a real confirmation, not an
assumed one.

## What "default-off" means at the code level (context for your own
verification step)

Independently re-confirming what I already verified when reviewing PR
#95, since your own "verify zero jobs run" step should check both of
these, not just service-level idleness:

1. `SCHEDULER_WORKER_ENABLED` unset (or `false`) → `create_worker_scheduler()`
   returns `None` before ever calling `.start()` — the process logs
   `scheduler_worker_disabled no_jobs_will_run` and idles.
2. Even if that flips true, `SCHEDULER_JOB_ALLOWLIST` unset/empty raises
   `RuntimeError` at startup rather than falling through to "run
   everything" — fails closed, not open.

So connecting credentials alone, with `SCHEDULER_WORKER_ENABLED` left
unset on the new service, should not execute any job. Your own
verification (checking the actual deployed log line, not just trusting
the code) is still the real gate — I have no Railway visibility to
confirm that myself.

## Verification

- Human confirmation: explicit "Yes, authorize" via a direct question
  naming the exact scope (prod DB/storage/Supabase/provider/monitoring/
  signing variable references, default-off config, connected to `main`).
- Code-level re-check of the default-off guard: see PR #95's own review
  comment (already posted) for the full trace + regression-catch
  verification performed before merge.

## Known gaps / risks

Same as stated in STATE.md after PR #95: no Railway scheduler-worker
service was live before this authorization (you reported it as blank/
inert — no source, no deployment, no replicas, no credentials, no jobs).
This authorization only unblocks wiring credentials to it; it does not by
itself authorize enabling any job. A separate, explicit step is still
needed before flipping `SCHEDULER_WORKER_ENABLED` or populating
`SCHEDULER_JOB_ALLOWLIST` for any real job — per the phased plan in
`docs/SCHEDULER_WORKER_ROLLOUT.md`.

## Next action

Proceed with provisioning `CRAVE-scheduler`: reference the authorized
production variables, keep it default-off, connect it to `main`, deploy,
and verify the disabled log line yourself against the real service (not
just the code). Report back the deployed SHA and the exact log line you
observed. Do not enable any job or set `SCHEDULER_JOB_ALLOWLIST` as part
of this step — that's a separate, later authorization per the rollout
doc's phased plan (starting with `moderation_queue_health_check`).
