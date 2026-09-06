# Supabase production configuration runbook

Permanent runbook (not a dated audit), same structure as
`docs/SENTRY_PRODUCTION_VERIFICATION.md` and
`docs/RAILWAY_PRODUCTION_ENV_VERIFICATION.md`. Confirms the production
Supabase project is the one actually wired up, and that sign-in works
end-to-end against it — not just that the code path exists.

## Why this exists

Backend auth verification (`backend/app/core/user_auth.py`) fetches
Supabase's public JWKS at `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`
and verifies the bearer token's signature (ES256/RS256 only,
deliberately excluding HS256 — a shared-secret algorithm has no
business being verifiable from a public JWKS) and audience. There is
no separate "JWT secret" to configure — Supabase signs with an
asymmetric key, so the wrong `SUPABASE_URL` doesn't fail loudly, it
just means every token gets checked against the *wrong project's*
public keys, which will simply reject everything with a generic
`401 Invalid token` — indistinguishable from a real auth bug unless
this is checked directly.

`SUPABASE_SERVICE_ROLE_KEY` (backend-only, `os.getenv`, used in
`app/services/account/account_deletion_service.py`) is the other
half — it deletes the Supabase auth identity itself during account
deletion, and must never be the same project as a dev/staging Supabase
instance or account deletion will silently do nothing to the real
user record.

## Prerequisites

- Access to the Supabase dashboard for the intended production project.
- Access to Railway (backend `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`)
  and to the EAS/build environment (`EXPO_PUBLIC_SUPABASE_URL`,
  `EXPO_PUBLIC_SUPABASE_ANON_KEY`).

## Proof 1 — all four Supabase values point at the same, real production project

- Supabase dashboard → intended production project → Project Settings
  → API.
- Confirm `Project URL` matches **both** `SUPABASE_URL` (Railway,
  backend) and `EXPO_PUBLIC_SUPABASE_URL` (EAS production env,
  frontend) exactly.
- Confirm the `anon`/`public` key matches `EXPO_PUBLIC_SUPABASE_ANON_KEY`.
- Confirm the `service_role` key matches `SUPABASE_SERVICE_ROLE_KEY`
  (Railway only) — and confirm it is **not** present in any
  `EXPO_PUBLIC_*` variable anywhere (already checked once in
  `docs/PRODUCTION_CREDENTIAL_LEAKAGE_AUDIT_2026-09-06.md`, PASS — this
  re-check is specifically "is it still true for the production values
  actually in use," not a repeat of the static-analysis pass).

**Pass:** all four values reference one single production project, and
`service_role` is backend-only.
**Fail:** if `SUPABASE_URL`/`EXPO_PUBLIC_SUPABASE_URL` mismatch (e.g.
backend points at a staging project, frontend at production) — every
request will fail to authenticate. Fix both to the same project and
redeploy/rebuild.

## Proof 2 — Google/Apple OAuth providers are configured for this project

- Supabase dashboard → Authentication → Providers.
- Confirm Google and Apple sign-in are enabled **on the production
  project specifically** (provider configuration is per-project, not
  inherited from a dev project) — redirect URIs, client IDs/secrets,
  and (for Apple) the Services ID/Key ID/Team ID are all filled in.
- Confirm the redirect URI registered with each provider matches this
  app's actual scheme (`crave://`, per `app.json`'s `"scheme": "crave"`).

**Pass:** a real sign-in attempt against this project succeeds for
both Google and Apple.
**Fail:** an OAuth provider misconfigured on this specific project is
a common "worked in dev, fails in prod" trap — dev/staging Supabase
projects often get providers configured first and production is
missed. Fix the specific provider's config in the Supabase dashboard.

## Proof 3 — end-to-end sign-in against production

- Using a production (or production-pointed EAS preview) build, sign in
  with a real Google account and a real Apple ID.
- Confirm the resulting bearer token is accepted by the production
  backend (a subsequent authenticated request, e.g. `GET /api/v1/...`
  succeeds, not a 401).

**Pass:** both sign-in methods complete and the app reaches an
authenticated state against the real production backend.
**Fail:** work backward — if the OAuth redirect itself fails, it's
Proof 2; if OAuth succeeds but the backend rejects the token, re-check
Proof 1 (`SUPABASE_URL` mismatch between the two sides is the most
common cause of "OAuth succeeded, API calls still 401").

## After running this

Record the result: append a dated Result section to this file, and
update `docs/MASTER_RELEASE_CERTIFICATION_MATRIX.md`'s Section 4.2
status.
