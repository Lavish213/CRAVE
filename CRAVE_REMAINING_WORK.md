# CRAVE — Remaining Work Log

This is the companion to `CRAVE_REMEDIATION_PLAN.md`. That document was the
plan; this document is the honest accounting of what actually got fixed in
code during this session, what's left, and — critically — everything that
could **not** be done because this session had no shell/bash access at any
point (no `pip install`, `npm install`, `alembic upgrade`, `git`, or test
execution of any kind, in either the audit phase or the remediation phase).
Every fix below was written and reviewed by hand, not compiled or run.

## Corrections to the earlier remediation plan

The original audit assumed these files were dead code. A verification pass
during cleanup found that assumption was **wrong** — they're still live and
were correctly left untouched:

- `app/services/scoring/recompute.py` — still imported by `app/workers/master_worker.py` and `app/services/scoring/compute_master_score.py`.
- `app/workers/master_worker.py` — has its own CLI entrypoint (`run_master_worker.py`) and is explicitly marked active elsewhere in the repo.
- `app/workers/discovery_worker.py`, `truth_rebuild_worker.py`, `search_index_worker.py` — standalone long-running workers, each still active.

If you're referencing the old plan document, disregard its claims about
these five files.

## Must do before anything else works in production

1. **Read the actual Railway crash log.** The deployment has reportedly been
   crashed for ~2 months. Nothing in this session could see *why* — that
   requires the Railway dashboard/CLI directly.
2. **Set `SUPABASE_JWT_SECRET`.** This session added real JWT verification
   (`app/core/user_auth.py`) and a startup guard (`app/main.py`,
   `_validate_prod_config()`) that now **refuses to start in prod** if this
   is unset. Get it from Supabase → Project Settings → API → JWT Settings →
   JWT Secret.
3. **Replace `SECRET_KEY`.** Still the literal placeholder
   `"your_secret_key_here"` in `backend/.env` — the same startup guard
   blocks prod boot until this is a real random value.
4. **Rotate every secret currently sitting in plaintext in `backend/.env`**
   (API_KEY, GOOGLE_PLACES_API_KEY, SUPABASE_SERVICE_ROLE_KEY) if this file
   has ever been committed to git history. Move to Railway's environment
   variables instead of a checked-in `.env`.
5. **Confirm `DATABASE_URL`** actually points at a live, reachable Postgres
   instance. Railway shows the variable is set, but its value was masked in
   the screenshot shared earlier and was never independently verified.
6. **Run `alembic upgrade head`** against that real database. Two
   migrations exist that have never been applied anywhere:
   `k1l2m3n4o5p6_add_menu_snapshots_table.py` and
   `l1m2n3o4p5q6_add_job_runs_and_candidate_failure_tracking.py`.

## Frontend — action required, not just code

7. **`node_modules` is stale.** It exists on disk with real installed
   packages, but `node_modules/expo-location/package.json` still reports
   `55.1.8` even though `package.json` was corrected to `~19.0.8` this
   session (the version SDK 54 actually bundles). The declared dependency
   is fixed; the installed one isn't. Run `npm install` (or
   `npx expo install --fix`).
8. **`package-lock.json` is now out of sync** with `package.json` for the
   same reason (expo-location, expo-auth-session, expo-linking, expo-router,
   expo-web-browser versions all changed). The new CI workflow uses
   `npm ci`, which **will fail** until someone runs `npm install` locally
   and commits the regenerated lockfile.
9. **A full native rebuild is required**, not just a JS/OTA update. Two
   changes this session only take effect through `expo prebuild` (or a new
   EAS build): the expo-location version bump, and the newly-added
   `expo-location` config plugin in `app.json` (which injects the iOS
   `NSLocationWhenInUseUsageDescription` string — without it, the very
   first location permission request crashes the app on iOS).
10. **Verify `react-native-worklets`.** Its version in `package.json`
    (`0.7.1`) doesn't match what Expo SDK 54's own reference bundle lists
    (`0.5.1`), but `react-native-reanimated@~4.1.1` has a strict version
    contract with worklets and downgrading it blind (with no way to run
    `npm install` and test) risked breaking Reanimated outright. Left
    untouched — run `npx expo-doctor` or `npx expo install --check` to
    confirm the right pairing.
11. Nothing in this session was compiled. `search.tsx`, `hitlist.tsx`,
    `useTrending.ts`, `MapBottomSheet.tsx`, `PlaceCardCompact.tsx`,
    `more.tsx`, and the new `+not-found.tsx` were all hand-reviewed for
    syntax/type correctness but never run through `tsc` or the Metro
    bundler. Run `npx tsc --noEmit` locally before shipping.

## Backend cleanup — annotated, not deleted

12. ~27 confirmed-dead files (old `app/pipeline/*` candidate/AOI pipeline,
    the queue-based `app/services/enrichment/worker.py` +`enqueue.py`, dead
    discovery connectors, the whole `app/services/aoi/` package, etc.) were
    marked with a deprecation header comment each — the same style already
    used in `app/api/routes/menus.py`. None were deleted or emptied, since
    there was no way to run the app afterward to confirm nothing broke.
    They're safe to actually delete whenever you're ready; each header
    explains what confirmed it's dead.
13. No automated test suite exists in the backend at all (zero files under
    any `tests/` directory). The new CI workflow only does a syntax
    compile + import-sanity check — real test coverage is still unstarted.

## Deliberately not automated (needs a human decision)

14. **Google Places ingestion was not wired into the scheduler**, even
    though `scripts/run_google_ingest.py` + `GooglePlacesIngest` are fully
    functional. Google Places charges per request, and scheduling
    unattended, recurring city-wide grid scans could run up real, unbounded
    billing without anyone signing off on a budget. If you want this
    automated, decide on a cadence/budget first, then either wire it into
    `app/scheduler.py` yourself or ask for it explicitly. What *was* fixed:
    the client now correctly detects and stops on `OVER_QUERY_LIMIT` /
    `REQUEST_DENIED` instead of silently returning zero results forever
    (see `app/services/ingest/google_places_ingest.py`).
15. **Grubhub session cookies expire and need periodic manual refresh** —
    this is a scraped session, not an API integration, so it can't be made
    to renew itself without a real Grubhub login flow.
16. **`.worktrees/frontend-productization/`** is a leftover git worktree
    with its own duplicate `railway.json`/`frontend/` copy sitting in the
    repo. Nobody touched anything inside it this session, but it's dead
    weight — clean it up with `git worktree remove` when convenient.
17. `railway.json` itself was checked and looks correct as-is (Railpack
    builder, healthcheck on `/health`, which exists) — no changes were
    needed there.

## Product decisions, not bugs

18. "Rate CRAVE" now reads "Coming soon" instead of silently doing nothing
    on tap — there's no App Store/Play Store listing yet since the app
    isn't published. Wire the real store URL in once it exists
    (`app/(tabs)/more.tsx`).
19. "How CRAVE Works" now opens a plain `Alert` with real explanatory copy
    instead of doing nothing — a proper onboarding modal would be a better
    long-term experience but is a real feature to design, not a quick fix.
20. Push notifications remain fully unbuilt ("Coming soon" in More).
21a. **Action required on Railway: provision a second service for the
    scheduler.** Root-caused a persistent "map/feed times out even on good
    Wi-Fi" report: the web service runs as a single uvicorn worker
    (`railway.toml`'s startCommand has no `--workers` flag) with
    APScheduler's BackgroundScheduler running in threads inside that same
    process. CPU-bound job work (image resize/hash, HTML parsing, OCR)
    competes with the GIL for time the request-handling event loop needs —
    confirmed via `job_runs`: a single menu_enrichment run took 3h21m while
    image_ingestion ran every 20 minutes concurrently, both in the same
    process serving map/feed API requests. Code is now in place
    (`app/scheduler_worker.py`, `settings.run_embedded_scheduler`) but
    doesn't take effect until you do this on Railway's dashboard:
    1. New service in the same Railway project, same repo/branch.
    2. Override its start command to: `cd backend && python -m app.scheduler_worker`
       (no `alembic upgrade head` needed here — the web service's
       startCommand already runs migrations).
    3. Copy every env var the web service has (DATABASE_URL,
       GOOGLE_PLACES_API_KEY, R2_*, SUPABASE_*, etc.) onto this new service —
       it runs the identical jobs, just in its own process.
    4. Once that new service is confirmed running (check its logs for
       `scheduler_worker_started jobs=8`), set `RUN_EMBEDDED_SCHEDULER=false`
       on the WEB service specifically and redeploy it. Skipping this step
       means both processes run every job — double-billing Google
       Places/Vision and double-writing data.
    Until step 4 is done, nothing changes (the web service still runs jobs
    embedded, same as before — this is backward compatible by design).
21. **Email + phone number sign-up/sign-in is not built.** `AuthSheet.tsx`
    only offers "Continue with Apple" / "Continue with Google" — there's no
    email+password or phone/OTP option, so anyone without one of those two
    accounts can't sign up at all. Needed for broader sign-up capture (and
    for collecting emails/numbers directly rather than only through an OAuth
    provider). Requires: enabling email + phone providers in the Supabase
    dashboard (Authentication → Providers), a phone OTP send/verify flow
    (Supabase supports this via an SMS provider like Twilio, which needs its
    own account/billing), and new UI in `AuthSheet.tsx` for both. Not started.

## What was verified, for confidence

- `NOMINATIM_CONTACT` was added (`backend/app/config/settings.py`,
  `backend/.env`) so Nominatim's usage-policy-required identifying
  User-Agent can be set — currently blank, so geocoding requests still use
  a non-compliant User-Agent until someone fills in a real contact email or
  URL.
- Nominatim rate limiting turned out to **already be handled** by the
  existing generic per-domain throttle in
  `app/services/network/domain_rate_limiter.py` (2s floor per domain,
  stricter than Nominatim's 1 req/s policy) — no change was needed there,
  just documentation added so it's not re-flagged as a bug later.
- `starlette>=1.0.0` in `backend/requirements.txt` was a literally
  impossible constraint (starlette has never released a 1.0 — latest is the
  0.5x series) that would make `pip install` fail outright. Fixed to
  `starlette>=0.40.0,<1.0.0`. Other version floors in that file were
  spot-checked against real PyPI release history and are fine.
