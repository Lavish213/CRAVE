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
already exists: `GET /debug/sentry-test`
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
