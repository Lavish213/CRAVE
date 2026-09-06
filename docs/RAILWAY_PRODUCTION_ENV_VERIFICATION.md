# Railway production environment verification runbook

Handoff doc — not an engineering phase. Formalizes
`backend/app/main.py`'s own `_validate_prod_config()` hard-fail check
into a runbook a human with Railway dashboard access can run, the same
way `docs/SENTRY_PRODUCTION_VERIFICATION.md` did for Sentry
specifically. This is the permanent verification procedure for this
check, not a one-off dated audit — re-run it whenever the production
Railway service's environment variables change.

## Why this exists

`app/main.py`'s `_validate_prod_config()` already refuses to boot
(`raise RuntimeError`, not just a log line) if, when `APP_ENV=="prod"`:

- `SECRET_KEY` is still `"change-me-in-production"` or under 32 bytes
- `SUPABASE_URL` is unset
- `CORS_ALLOW_ORIGINS` is `"*"`
- `DATABASE_URL` is unset
- `API_KEY` is unset

This is real, load-bearing protection — but it **only runs at all**
if `APP_ENV` is actually `"prod"` on the production service
(`_validate_prod_config`'s first line is `if not settings.is_prod:
return`). If `APP_ENV` were left at its default (`"dev"`) or set to
`"staging"` on the real production service, this entire gate silently
no-ops and the service would boot fine with an insecure `SECRET_KEY`,
an open `API_KEY` bypass (`require_api_key` allows all requests when
`API_KEY` is unset — see `app/core/auth.py`), and so on. Confirming
`APP_ENV=prod` is therefore the single highest-leverage variable to
verify — everything else on this list is enforced automatically once
that one is correct, but nothing is enforced until it is.

## Proof 1 — `APP_ENV` is actually `prod` on the production service

- Railway dashboard → backend service → **production environment** →
  Variables tab.
- Confirm `APP_ENV` is exactly `prod` (not `production`, not unset,
  not inherited from a shared/default variable group meant for
  staging).

**Pass:** `APP_ENV=prod`.
**Fail:** anything else — every check below this one is currently
being silently skipped at every boot. This is the one item on this
runbook where "fail" doesn't just mean "one thing is misconfigured,"
it means "nothing downstream has actually been verified by the app
itself yet." Fix this first, then re-run Proof 2.

## Proof 2 — the app actually enforces its own checklist (an indirect check)

Rather than manually re-deriving what `_validate_prod_config()`
already checks, the cleanest verification is to confirm the service
is *currently running* — since with `APP_ENV=prod` now set, the
service could only have booted successfully if every one of
`SECRET_KEY`/`SUPABASE_URL`/`CORS_ALLOW_ORIGINS`/`DATABASE_URL`/
`API_KEY` already passed the gate.

```bash
curl -s https://<prod-backend-host>/health
curl -s https://<prod-backend-host>/api/v1/debug/version
```

- `/health` responding (not connection-refused/timeout) means the
  process is up.
- `/api/v1/debug/version` responding with a real `commit` field
  confirms it's actually serving the deployment you expect, not a
  stale/crashed instance still answering from before the `APP_ENV`
  change.

**Pass:** both endpoints respond, `/api/v1/debug/version`'s `commit`
matches the expected deploy.
**Fail:** if the service **won't boot at all** after setting
`APP_ENV=prod` — this is `_validate_prod_config()` doing its job.
Read the Railway deploy logs for the specific `startup_validation_failed
prod_config=...` line(s) it logs before raising — each names exactly
which variable is still wrong (e.g. `"SECRET_KEY is still the default
placeholder value"`, `"API_KEY is unset — all write endpoints are open
to unauthenticated requests"`). Fix each named variable, redeploy,
repeat until it boots.

## Proof 3 — spot-check the variables directly (belt and suspenders)

Even though Proof 2 confirms the gate passed, directly eyeballing the
values in the Railway Variables tab catches things the gate can't
(e.g. a `SECRET_KEY` that's 32+ random bytes but was pasted from a
shared password manager entry also used elsewhere, or a
`CORS_ALLOW_ORIGINS` that's technically not `"*"` but is broader than
intended):

- `SECRET_KEY` — 32+ bytes, unique to this project, not reused from
  any other service or a placeholder-looking value.
- `DATABASE_URL` — points at the real production Postgres instance,
  not a dev/staging database.
- `SUPABASE_URL` — matches the production Supabase project (cross-
  reference against Section 4.2 of the Master Release Certification
  Matrix, which covers Supabase specifically).
- `CORS_ALLOW_ORIGINS` — empty (native-app-only, no browser client) or
  an explicit, narrow comma-separated list — never `*`.
- `API_KEY` — set, and matches `EXPO_PUBLIC_API_KEY` in the production
  frontend build (this is a low-value gate by design, not a real
  secret — see `frontend/.env.example`'s own comment — but it must
  still be *set*, since an unset `API_KEY` opens every write endpoint
  with no auth at all).

**Pass:** every value above is production-appropriate on inspection,
not just "present."
**Fail:** correct the specific variable; if it required changing
`SECRET_KEY` or `DATABASE_URL`, expect existing signed tokens
(ranking comparison-flow tokens, see `app/services/personal_ranking/
ranking_service.py`) to invalidate — that's expected, not a bug.

## After running this

Record the result: append a dated Result section to this file, and
update `docs/MASTER_RELEASE_CERTIFICATION_MATRIX.md`'s Section 4.1
status from `BLOCKED ON ACCESS` to `PASS` or `FAILED` (with the
failure-history convention Section 12 defines, if it fails). The
matrix is the controlling document — a result recorded only here
doesn't close the item there.
