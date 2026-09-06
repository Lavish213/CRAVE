# Sentry production verification checklist

Handoff doc — not an engineering phase. This is a one-time operational
check for whoever has Railway dashboard access (Codex or a human
operator), not something a repo-only session can run itself: it needs
the production Railway console and the Sentry project dashboard.

## Why this exists

Phase 7 fixed the in-app privacy policy's crash-reporting claim (it no
longer asserts a frontend Sentry SDK that doesn't exist) and confirmed
the backend's Sentry wiring is real: `backend/app/main.py` calls
`sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.app_env,
send_default_pii=False, ...)` whenever `SENTRY_DSN` is set, and its
`global_exception_handler` calls `sentry_sdk.capture_exception(exc)` on
every unhandled error.

Confirming the code path exists is not the same as confirming it's
*configured and actually delivering events* in the real production
environment. That's the one thing left to check, and it's an infra
check, not a code change.

## Proof 1 — `SENTRY_DSN` is actually set in production

- Railway dashboard → backend service → **production environment** →
  Variables tab.
- Confirm `SENTRY_DSN` is present, non-empty, and shaped like a real
  DSN (`https://<key>@<org>.ingest.sentry.io/<project_id>`).
- Also confirm `APP_ENV=prod` on that same service. `sentry_sdk.init()`
  tags every event with `environment=settings.app_env`
  (`backend/app/main.py`) — a wrong `APP_ENV` will make Proof 3 show
  events tagged `dev`/`staging` even from the real production service.

**Pass:** both vars present and correct.
**Fail:** `SENTRY_DSN` empty → `if settings.sentry_dsn:` in
`app/main.py` never calls `sentry_sdk.init()` at all. Nothing
downstream in this checklist will work until this is fixed. Stop here.

## Proof 2 — trigger one controlled exception

The repo already ships a purpose-built endpoint for exactly this:
`GET /debug/sentry-test` (`backend/app/api/v1/routes/debug.py`). It
raises a static `RuntimeError` with a fixed, non-sensitive message — no
user data, no request input reflected in it — which flows through
`global_exception_handler` → `sentry_sdk.capture_exception(exc)`.

It's gated by `require_debug_api_key` (header `x-debug-api-key`, env
var `DEBUG_API_KEY` — confirm that's also set on the same Railway
service; it fails closed with a 503 if unset, per that dependency's own
docstring in `backend/app/core/auth.py`).

```bash
# optional first: confirms which deployment/commit you're actually
# hitting before firing the test exception
curl -s https://<prod-backend-host>/debug/version

curl -s -o /dev/null -w "%{http_code}\n" \
  -H "x-debug-api-key: $DEBUG_API_KEY" \
  https://<prod-backend-host>/debug/sentry-test
```

**Pass:** HTTP `500` — that is the correct/expected outcome; the
endpoint always fails on purpose.
**Fail:** `401` = wrong/missing debug key; `503` = `DEBUG_API_KEY`
itself isn't configured on this service (a separate fix from
`SENTRY_DSN`).

## Proof 3 — verify the event landed, correctly tagged, with no PII

In the Sentry project dashboard, filter Issues by `environment:prod`
and search for "CRAVE debug/sentry-test."

Confirm:

- One new event appears within roughly a minute of the curl call.
- Its `environment` tag reads `prod`, not `dev`/`staging`.
- Its "Request"/"User" context shows **no** email, name, IP, or the
  `x-debug-api-key` header value. `send_default_pii=False` is set
  explicitly in `sentry_sdk.init()` — this step confirms that's
  actually true in a live event, not just present in source.

**Pass:** event found, correctly tagged, no PII/secret fields visible
in it.

**Fail — no event arrives.** Check in this order (each step rules out
the layer before it):

1. Re-confirm the curl in Proof 2 actually returned `500`, not
   `401`/`503`/a timeout.
2. Re-check `SENTRY_DSN` for a typo or a DSN pointing at the wrong
   Sentry project.
3. Check whether the Railway service actually **redeployed** after
   `SENTRY_DSN` was set. `sentry_sdk.init()` only runs once, at process
   startup (`app/main.py` module load) — setting the var without a
   redeploy leaves the already-running process uninitialized.
4. Check Sentry's own project-level rate-limit/spike-protection
   settings (unlikely to matter for one single test event, but quick
   to rule out).
5. If everything above checks out and still nothing arrives, the gap
   is outbound network egress from the Railway container to Sentry's
   ingest host — a firewall/network-policy question for whoever
   manages the Railway project, not a backend code fix.
