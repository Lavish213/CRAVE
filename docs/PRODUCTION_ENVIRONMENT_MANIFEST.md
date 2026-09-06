# Production environment manifest

Canonical list of every environment variable/service configuration
CRAVE's production deployment depends on — **not the values
themselves**, just what exists, where it belongs, and whether it's a
secret. Purpose: whoever runs certification should never need to
rediscover configuration architecture by reading source — they read
this table and the matching runbook instead.

Format: `NAME` — required? — where it lives — is it a secret? —
expected shape/value — verifying runbook.

## Backend (Railway)

| Variable | Required | Where | Secret? | Expected | Runbook |
|---|---|---|---|---|---|
| `APP_ENV` | Yes | Railway | No | `prod` | `RAILWAY_PRODUCTION_ENV_VERIFICATION.md` |
| `SECRET_KEY` | Yes | Railway | **Yes** | 32+ random bytes, never the placeholder, unique to this project | `RAILWAY_PRODUCTION_ENV_VERIFICATION.md` |
| `DATABASE_URL` | Yes | Railway | **Yes** | `postgresql://...` pointing at the real production Postgres | `RAILWAY_PRODUCTION_ENV_VERIFICATION.md` |
| `CORS_ALLOW_ORIGINS` | Yes (or explicitly empty) | Railway | No | empty (native-app-only) or an explicit narrow list — never `*` | `RAILWAY_PRODUCTION_ENV_VERIFICATION.md` |
| `API_KEY` | Yes | Railway | Low-value (ships in client bundle as `EXPO_PUBLIC_API_KEY` — not a real secret, but must still be *set*) | matches `EXPO_PUBLIC_API_KEY` below | `RAILWAY_PRODUCTION_ENV_VERIFICATION.md` |
| `SENTRY_DSN` | Yes (if Sentry is the chosen observability answer) | Railway | **Yes** | a real Sentry DSN for the production project | `SENTRY_PRODUCTION_VERIFICATION.md` |
| `DEBUG_API_KEY` | Yes | Railway | **Yes** | a server-only secret, never referenced by any `EXPO_PUBLIC_*` var | `SENTRY_PRODUCTION_VERIFICATION.md` |
| `SUPABASE_URL` | Yes | Railway | No (public project URL) | matches the production Supabase project, and `EXPO_PUBLIC_SUPABASE_URL` below | `RUNBOOK_SUPABASE_PRODUCTION.md` |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Railway | **Yes — never client-side** | the production project's service_role key | `RUNBOOK_SUPABASE_PRODUCTION.md` |
| `R2_ACCOUNT_ID` | Yes | Railway | No | the production Cloudflare account ID | `RUNBOOK_R2_PRODUCTION.md` |
| `R2_ACCESS_KEY` / `R2_SECRET_KEY` | Yes | Railway | **Yes** | scoped to the production bucket only | `RUNBOOK_R2_PRODUCTION.md` |
| `R2_BUCKET` | Yes | Railway | No | the production bucket name | `RUNBOOK_R2_PRODUCTION.md` |
| `R2_PUBLIC_BASE_URL` | Yes | Railway | No | the bucket's real public-serving domain, not the S3 API endpoint | `RUNBOOK_R2_PRODUCTION.md` |
| `google_places_api_key` (env: likely `GOOGLE_PLACES_API_KEY`) | Yes (if Places ingestion runs in prod) | Railway | **Yes** | a server-only key, distinct from the Android Maps key | `RUNBOOK_GOOGLE_MAPS_PLACES_PRODUCTION.md` |
| `nominatim_contact` | Optional | Railway | No | a real contact email/URL, required by Nominatim's usage policy if that provider is used | n/a (low-risk config) |
| `redis_url` | Optional | Railway | **Yes, if set** | blank disables Redis (in-memory only) — confirm this is the intended production posture | n/a |
| `run_embedded_scheduler` / `scheduler_worker_enabled` / `scheduler_job_allowlist` | Depends on deployment topology | Railway | No | see `app/config/settings.py`'s own comments on the single-service vs. split-worker tradeoff | n/a (operational topology, not a security item) |

## Frontend (EAS build-time / `EXPO_PUBLIC_*`)

All `EXPO_PUBLIC_*` vars ship inside the compiled client bundle —
**none of these are real secrets**, per `frontend/.env.example`'s own
header comment. Listed as "secret?" = No throughout for that reason,
even though they must still be *correct*.

| Variable | Required | Where | Secret? | Expected | Runbook |
|---|---|---|---|---|---|
| `EXPO_PUBLIC_API_URL` | Yes | EAS production env | No | the real production Railway backend URL | — |
| `EXPO_PUBLIC_API_KEY` | Yes | EAS production env | No (low-value gate) | matches backend `API_KEY` | `RAILWAY_PRODUCTION_ENV_VERIFICATION.md` |
| `EXPO_PUBLIC_SUPABASE_URL` | Yes | EAS production env | No | matches backend `SUPABASE_URL` | `RUNBOOK_SUPABASE_PRODUCTION.md` |
| `EXPO_PUBLIC_SUPABASE_ANON_KEY` | Yes | EAS production env | No (anon key is public-by-design) | matches the production Supabase project's anon key | `RUNBOOK_SUPABASE_PRODUCTION.md` |
| `GOOGLE_MAPS_ANDROID_API_KEY` | Yes (Android only) | EAS build-time env / EAS secret | No (ships in binary, but restricted by package+SHA-1) | the Android-restricted Maps key | `RUNBOOK_GOOGLE_MAPS_PLACES_PRODUCTION.md` |

## Native/build identity (not env vars, but load-bearing)

| Item | Where | Expected | Runbook |
|---|---|---|---|
| iOS bundle identifier | `frontend/app.json` (`ios.bundleIdentifier`) | `com.crave.app`, matching Apple Developer registration | `RUNBOOK_EAS_SIGNING_PRODUCTION_BUILD.md` |
| Android package name | `frontend/app.json` (`android.package`) | `com.crave.app`, matching Play Console registration | `RUNBOOK_EAS_SIGNING_PRODUCTION_BUILD.md` |
| EAS project ID | `frontend/app.json` (`extra.eas.projectId`) | a real, non-placeholder UUID | repo inspection only (already PASS, matrix 5.2) |
| iOS signing cert/provisioning | EAS credentials / Apple Developer | valid, non-expired, matches bundle ID | `RUNBOOK_EAS_SIGNING_PRODUCTION_BUILD.md` |
| Android upload keystore | EAS credentials | a real production keystore, not a debug one | `RUNBOOK_EAS_SIGNING_PRODUCTION_BUILD.md` |
| Android Maps key SHA-1 restriction | Google Cloud Console | matches the production signing cert's SHA-1 | `RUNBOOK_GOOGLE_MAPS_PLACES_PRODUCTION.md` |

## Third-party consoles this deployment depends on

| Service | What it's for | Console |
|---|---|---|
| Railway | Backend hosting, Postgres | railway.app dashboard |
| Supabase | Auth (Google/Apple sign-in), JWT verification | supabase.com dashboard |
| Cloudflare R2 | Photo/video object storage | Cloudflare dashboard |
| Google Cloud | Maps SDK (Android), Places API | Google Cloud Console |
| Expo/EAS | Build, signing credentials, push delivery | expo.dev dashboard |
| Sentry (if enabled) | Backend error monitoring | sentry.io dashboard |
| Apple Developer | iOS signing, App Store Connect | developer.apple.com |
| Google Play Console | Android signing/submission, Data Safety | play.google.com/console |

## Maintenance

Add a row here the moment a new environment variable or third-party
service is introduced anywhere in the stack — this manifest and the
provider/data-flow inventory (`docs/PROVIDER_DATA_FLOW_INVENTORY.md`)
are the two documents that should make "what does this app depend on
externally" answerable without re-reading the codebase.
