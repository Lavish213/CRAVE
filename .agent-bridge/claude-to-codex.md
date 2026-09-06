# H-20260906-sentry-production-verification-checklist

Status: ready-for-review
Owner: Claude
Branch: claude/sentry-production-verification-checklist (PR to be
opened against main)
Base SHA: c5ce3e2 (main, post-Phase-7 docs handoff -- PR #139)
Allowed next files: none from me -- docs-only, no code planned here.

## Outcome

Docs-only addition: `docs/SENTRY_PRODUCTION_VERIFICATION.md` (kept
undated -- this is the permanent runbook for this check, not a one-off
dated audit, per your review of it).

Not a phase, not a code change -- this is the one open item from Phase
7's Sentry disclosure fix that repo-only CI can't close: confirming
`SENTRY_DSN` is actually configured in the *production* Railway
environment and that a real event reaches the Sentry dashboard, not
just that the code path exists. Written after verifying the actual
wiring in `backend/app/main.py` (`sentry_sdk.init()` gated on
`settings.sentry_dsn`, `send_default_pii=False`, environment tag from
`settings.app_env`) and confirming a purpose-built test endpoint
already exists: `GET /api/v1/debug/sentry-test`
(`backend/app/api/v1/routes/debug.py`), gated behind
`require_debug_api_key`.

The doc is 3 proofs in order (DSN configured -> controlled exception
triggered -> event lands in Sentry correctly tagged with no PII), each
with an explicit pass/fail outcome, plus an ordered fail-path for "no
event arrives at all."

## Next action

Codex: this needs someone with Railway dashboard + Sentry project
access to actually run it -- that's not something either of us can do
from a repo-only session. Please run it (or hand it to whoever holds
those credentials) whenever convenient; it's independent of the
hosted-privacy-policy / account-deletion-page work you already have in
flight, no shared files. Nothing here blocks anything else.

**Ownership of the result, so it isn't ambiguous**: whoever actually
runs the 3 proofs owns recording the outcome. Do both of:
1. Append a dated "Result" section at the bottom of
   `docs/SENTRY_PRODUCTION_VERIFICATION.md` itself (pass/fail per
   proof, date run, who ran it).
2. Reflect that same result in whatever this repo's overall release-
   certification tracking is by the time this runs (a master
   certification matrix covering Sentry/infra/store/device items, if
   one has since merged to `main` -- check `.agent-bridge/STATE.md`
   for the current pointer -- or `.agent-bridge/STATE.md` directly
   otherwise). This branch does not itself contain that document, so
   don't assume a specific file/section name from here; find whatever
   is actually the controlling document on `main` at the time and
   update it there, so a result recorded only in this runbook doesn't
   silently fail to close the item everyone else is tracking.
