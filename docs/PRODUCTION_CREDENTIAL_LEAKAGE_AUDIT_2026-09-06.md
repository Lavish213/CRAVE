# Production credential leakage audit — 2026-09-06

Scope: committed secret material and hardcoded credentials only — not a
general security review. Answers one release-gate question: can
anything in this repository leak a real production credential, or let
a dev/test value slip into a production build?

Checked: committed `.env`-shaped files, hardcoded API
keys/tokens/passwords/DSNs/service-role keys/private keys/DB
URLs/cloud credentials, `EXPO_PUBLIC_*` misuse (anything sensitive
shipped to the client bundle), dev/staging/test URLs or debug bypasses
that could reach a production build, `app.json`/`app.config.js`/EAS
config exposure, GitHub Actions workflows for literal secrets instead
of `${{ secrets.* }}`, source/tests/fixtures/scripts/docs/data caches,
and `.gitignore` coverage. Git history was also checked for any secret-
shaped file ever committed and later removed.

## Findings

### SAFE — `frontend/.env.example`

All four vars are empty placeholders, all correctly `EXPO_PUBLIC_*`
(compiled into the client bundle, so nothing sensitive belongs there —
the file's own header comment says so). No real value present.

### SAFE — backend secret handling pattern (`app/config/settings.py`)

Every real secret (`sentry_dsn`, `supabase_url`, `redis_url`,
`google_places_api_key`, `cors_allow_origins`) defaults to `""` and is
read only from the environment — no hardcoded value anywhere in the
class. `R2_ACCESS_KEY`/`R2_SECRET_KEY` (`app/services/upload/
r2_client.py`) and `SUPABASE_SERVICE_ROLE_KEY` (`app/services/account/
account_deletion_service.py`) follow the same `os.getenv(...)` pattern,
no fallback literal.

### SAFE, but flagged as a dependency — `secret_key` default placeholder

`secret_key: str = "change-me-in-production"` (`app/config/
settings.py`) signs the ranking comparison-flow HMAC tokens (`app/
services/personal_ranking/ranking_service.py`). This is not a leaked
credential — it's a deliberate placeholder — because `app/main.py`'s
`_validate_prod_config()` hard-fails startup (`raise RuntimeError`,
does not just log) whenever `APP_ENV == "prod"` and `secret_key` is
still this placeholder, shorter than 32 bytes, `SUPABASE_URL` is
unset, `CORS_ALLOW_ORIGINS` is `"*"`, `DATABASE_URL` is unset, or
`API_KEY` is unset.

That gate only runs `if settings.is_prod`. **This makes the SAFE
verdict here conditional on Railway's production service actually
having `APP_ENV=prod` set** — not a repo-side leak, but a direct
dependency on the separate production-infrastructure-verification
work already planned (Railway env var check), not a new finding to
duplicate there.

### SAFE — dev-mode auth bypasses (`app/core/auth.py`, `app/core/
user_auth.py`)

Both bypasses (`require_api_key` when `API_KEY` is unset;
`user_auth`'s dev-fallback user when `SUPABASE_URL` is unset) are
additionally guarded by an explicit `not settings.is_prod` check in
the bypass condition itself, on top of the startup hard-fail above —
defense in depth, not reliant on a single check.

### SAFE — CI workflows (`ci.yml`, `codeql.yml`, `dependabot.yml`,
`ask-crave.yml`)

`ci.yml`'s only DB URLs are `postgresql://postgres@localhost:5432/
postgres` (a throwaway CI service container) and a local SQLite test
file — never production. `ask-crave.yml` uses `${{ secrets.
OPENAI_API_KEY }}` and `${{ vars.OPENAI_MODEL }}` correctly; no literal
secret in any workflow file.

### SAFE — Expo/EAS config (`app.json`, `eas.json`, `app.config.js`)

No embedded secrets. `GOOGLE_MAPS_ANDROID_API_KEY` is read from
`process.env` at build time (meant to be set as an EAS secret), not a
literal string in source control, per the file's own header comment.
`eas.projectId` and bundle/package identifiers are not sensitive.

### SAFE — Grubhub cookie-scraping tooling (`backend/scripts/
grab_grubhub_cookies.py`, `app/services/menu/fetchers/
grubhub_fetcher.py`)

All `GRUBHUB_COOKIES` / `GRUBHUB_PERIMETER_X` values shown are
docstring examples (`'_px2=abc...; _pxvid=def...'`) — placeholders,
not real captured session data. The script writes real captured
values only to `backend/.grubhub_env`, which is gitignored and
confirmed never committed (checked full git history, not just the
current tree). This tooling is a data-ingestion pipeline concern
(third-party site scraping), not part of the shipped mobile app or its
runtime API surface.

### SAFE — cached place data (`backend/data/raw/*.json`,
`backend/data/places/*.json`)

No `key`/`token`/`secret` fields present in any of the checked files.

### SAFE — `.gitignore` coverage

`.env`, `.env.*`, and `.grubhub_env` are all explicitly listed.

## Git history

`git log --diff-filter=A` for `.env`, `.env.*`, `*secret*`,
`*credential*`, `*.pem`, `*.p12`, `*.keystore`, `*.jks` across the
entire history returned zero results — no secret-shaped file was ever
committed and later removed.

## Release gate

**Production credential leakage: PASS.**

Nothing in this repository can leak a real production credential, and
no hardcoded dev/test value can reach a production build through
anything checked here. The one caveat (`secret_key`'s placeholder
default) is not a leak — it's an enforced hard-fail-on-boot gate whose
correctness depends on `APP_ENV=prod` actually being set on the
production Railway service, which is exactly the separate production-
infrastructure-verification step already planned, not a new item.
