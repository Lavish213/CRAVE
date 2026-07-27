# Crave — Full Remediation Plan

Audit-only synthesis. Nine audits across frontend, backend, map, menu, extraction pipeline, security, API contract, and deployment, each compared against how working production apps (Yelp/Beli-class consumer apps, standard data-pipeline startups) handle the same concerns. This document is the "what to do" — no code was changed for the new findings here.

**The one-line diagnosis:** Crave is not one broken app — it's a working skeleton (routes, models, schedulers, a real design system) surrounded by six or seven half-finished systems that were never wired in, plus a production service that has been crashed for two months with no alerting to notice. Getting "fully up and working" is mostly *wiring and operating* work, not rewriting.

---

## Phase 0 — Resuscitate production (do first, nothing else matters until this)

**How working apps do it:** the service runs, restarts itself on crash, exposes a `/health` endpoint that the platform probes, and pages a human when it goes down.

**Where Crave is:** Railway deployment crashed 2 months ago; nobody noticed. All five scheduled jobs, the API, everything — dead. `DATABASE_URL` is set in Railway (good) but the masked value is unverified. The Supabase "Crave" project has zero tables, confirming it's auth-only — the real Postgres lives wherever Railway's `DATABASE_URL` points.

**What to do:**
1. Open the crashed deployment's logs in Railway and read the actual crash error. (Everything below is contingent on this — the crash may itself be one of the bugs already found, e.g. bad requirements resolution or a missing env var.)
2. Confirm `DATABASE_URL` points at a real persistent Postgres, not blank/SQLite. If it was ever SQLite-on-Railway, assume historical data loss and plan a re-ingest.
3. Redeploy with the fixed code, run `alembic upgrade head` against the production DB (this applies the new `menu_snapshots` migration and verifies the migration graph is sound).
4. Add a `/health` endpoint check in Railway's service settings + restart policy.
5. Turn on Railway's notification emails / add an uptime ping (UptimeRobot/Betterstack free tier). The two-month blind spot is the single most dangerous finding in this entire audit — fix the feedback loop, not just the crash.

---

## A. Security — currently the worst area relative to standard practice

**How working apps do it:** mobile clients authenticate users with per-user bearer tokens (the Supabase JWT you already issue); the backend verifies the token and derives `user_id` from it; API keys are reserved for server-to-server calls; rate limiting is shared-state and keyed per user; internal endpoints are not public.

**Where Crave is (ranked by severity):**
1. **Full IDOR on all per-user data.** The backend never verifies a Supabase JWT anywhere — zero JWT/Bearer/verify code exists in `backend/app`. `user_id` is a plain client-supplied string on saves and hitlist routes (`saves.py`, `hitlist.py`). Anyone can read, create, or delete any user's saves by substituting a UUID.
2. **The API key is public.** `EXPO_PUBLIC_API_KEY` is compiled into the shipped app bundle; anyone who unzips the APK/IPA has it. Every `require_api_key` guard is decorative. Combined with #1, the entire per-user dataset is world-readable.
3. **Unauthenticated write + fetch primitive.** `POST /api/v1/share` has no auth and no rate limit and causes a background worker to fetch a client-supplied URL. `GET /api/v1/craves` dumps the latest 50 submitted URLs. `/enrichment/priority` and `/coverage/summary` expose internal catalog analytics publicly.
4. **Rate limiting is cosmetic.** In-memory per-process dict (multiplies per worker), IP-keyed (collides carrier-NAT users), applied to only 6 of 17 routers (not saves/hitlist/share/craves/image), and has an off-by-one bug that never records the first request of each window.
5. **Hardening gaps:** no CORS middleware, no security headers, `/docs` + `/openapi.json` public in prod, no body-size limits, `SECRET_KEY` defaults to a known string with no prod guard, raw `user_id` logged at INFO.
6. **Genuinely fine:** SQL is all ORM-parameterized (no injection), the image proxy is properly anchored to Google's domain (no SSRF), and the API-key comparison uses `hmac.compare_digest`.

**What to do (in order):**
1. Add a `get_current_user` FastAPI dependency that verifies the Supabase JWT (via Supabase JWKS or `SUPABASE_JWT_SECRET`) and derives `user_id` from the `sub` claim. Apply it to every saves/hitlist/craves/share route. Delete every client-supplied `user_id` parameter. This one change closes findings #1–#3's worst consequences.
2. Frontend: attach the Supabase session token as `Authorization: Bearer` on API calls (the session already exists in `authStore`).
3. Demote the API key: keep it only for genuinely server-to-server callers, or drop it. Stop treating it as security.
4. Replace the rate limiter with `slowapi` + Redis (Railway has one-click Redis), keyed on authenticated user ID with IP fallback, applied as global middleware.
5. Add: CORS allowlist, `docs_url=None` when `APP_ENV=prod`, a startup validator that hard-fails on default `SECRET_KEY` in prod, security-header middleware, request body limit at the proxy.
6. Rotate every secret currently in `backend/.env` (Google Places key, API key, Supabase service-role key) — they've been sitting in a plaintext file on disk and the Grubhub cookies are expired anyway. Move to Railway env vars only.

---

## B. Extraction / ingestion pipeline — the reason "hella scrapers" produce nothing

**How working apps do it:** acquisition (fetch from sources) runs on a schedule with per-source rate limits and backoff; candidates get deduped by a real entity matcher (name + address + geo distance + brand aliases); failures go to a dead-letter state with a recorded error instead of retrying forever; a job-runs table or metrics dashboard shows exactly what ran and what it produced; images and enrichment refresh continuously.

**Where Crave is:** Only five jobs are scheduled: promotion-of-existing-candidates (misnamed "discovery"), menu enrichment (thin extractor), score recompute, ranking, share parsing. **Nothing scheduled ever fetches new data from the outside world.** Candidate supply comes exclusively from human-run scripts (`run_osm_ingest.py`, `run_google_ingest.py`, etc.). The scheduled "discovery" job just drains a queue nothing refills. Additionally:

- `app/jobs/ingest_google.py` is a **zero-byte file**.
- The entire `app/pipeline/*` package (IngestRunner → CandidateBuilder → ClusterBuilder → PromotionEngine) is a dead parallel pipeline; its PromotionEngine returns dicts and never writes the DB.
- The real entity matcher (`entity/entity_matcher.py`) is only imported by dead code. Live dedup is `lower(name) == lower(name)` within a city — chain restaurants merge into one Place, near-duplicates slip through.
- `ImageWorker` (which is actually well-built: retry caps, block-listing, cache invalidation) is reachable only through `master_worker.py`, a `while True` process nothing launches.
- The AOI coverage brain (`services/aoi/*`), the license/permit/health-inspection connectors, `truth_engine.py`, the promotion-gate explainability path, and `coverage_report.py` are all complete-ish and all unwired.
- Google Places and Nominatim calls have no rate limiting, budget caps, or 429 handling (Nominatim's 1 req/s policy is violated inside the promotion loop — a ban risk).
- Failed candidates are retried every 5 minutes forever with no error recorded (`except: rollback; continue`).

**What to do:**
1. **Wire acquisition into the scheduler.** Pick the 1–2 sources that matter (Google Places ingest + OSM), turn the existing scripts' logic into scheduled jobs with sane cadences (e.g. nightly per city). Delete or implement the empty `ingest_google.py`.
2. **Schedule `ImageWorker` directly** (it's ready today — this is a two-line scheduler registration decision).
3. **Swap the live dedup to the real entity matcher** (`entity_match`) in `promote_service_v2` — it already exists; this is wiring, not building.
4. **Add failure tracking:** `failure_count` + `last_error` + `next_retry_at` columns on `discovery_candidates`; skip candidates past N failures. Stop the infinite silent retry loop.
5. **Add per-source rate limiting/backoff:** a token bucket for Google Places with a daily budget cap and 429 handling; 1 req/s + caching for Nominatim.
6. **Add a `job_runs` table** (job name, started, finished, counts, error) written by every scheduled job, and wire the existing `coverage_report.py` to run weekly. This is the minimum observability a data product needs.
7. **Delete the dead `app/pipeline/*` package and other confirmed-orphaned modules** (or move to an `attic/` folder) so future work stops landing in dead branches. This is the highest-leverage cleanup in the repo.
8. Decide the fate of the ambition modules (AOI engine, license/permit connectors): either schedule them behind a feature flag or remove them. Half-existing is the only wrong state.

---

## C. Menu system — from scrape to screen

**How working apps do it:** one extraction path, one canonical storage, one API route; extraction handles the messy real world (JS-rendered sites, PDFs, delivery-platform pages); places without a direct website still get menus via their delivery-platform URLs.

**Where Crave is (after this session's fixes):** the schema mismatch, duplicate route, and missing `menu_snapshots` migration are fixed in code but **not yet deployed or migrated**. Still open: the scheduled worker uses the thin extractor (single-fetch, no PDF/JS) while the capable one (`menu_extraction_router.py` — PDFs, hydration, GraphQL, browser escalation) only exists behind manual scripts; the worker only picks up places with `website IS NOT NULL`, skipping places whose only menu source is a Grubhub URL; Grubhub scraping depends on session cookies in `.env` that expire (already stale, dated April).

**What to do:**
1. Deploy the fixes; run the migration; verify one place's menu end-to-end (scrape → PlaceClaim → PlaceTruth → menu_items → `GET /places/{id}/menu` → app screen).
2. Route the scheduled `menu_worker` through `menu_extraction_router.extract_menu` (the capable path) instead of the thin inline chain — with a per-run cap so it can't blow the crawl budget.
3. Widen worker eligibility: `website IS NOT NULL OR grubhub_url IS NOT NULL OR menu_source_url IS NOT NULL`.
4. Replace cookie-dependent Grubhub scraping with something maintainable: either a scheduled cookie-refresh procedure with expiry alerting, or drop Grubhub as a source. Expired-cookie-silent-failure is the current state and it's invisible.
5. Add per-place menu extraction status to the `job_runs`/failure-tracking work in section B so "why doesn't this place have a menu" is answerable in one query.

---

## D. Map

**How working apps do it:** refetch on viewport change (debounced), radius derived from zoom, clustering for dense areas, pins carrying everything the detail sheet needs.

**Where Crave is:** all four of those were missing and were fixed in code this session (viewport refetch + debounce, zoom-aware radius, grid clustering, category/has_menu plumbed through). Remaining, untested-because-unrunnable:

**What to do:**
1. Build and run the app; exercise the map hard (pan across a city, zoom in/out fast, switch cities mid-flight) — the debounce/programmatic-move logic is exactly the kind of code that needs a device test.
2. Backend `has_menu`/category now flow into pins — verify the bottom sheet renders them and remove the duplicate tier label in `MapBottomSheet.tsx` (found, not yet fixed).
3. Longer-term: if a city exceeds ~1,000 pins, move clustering server-side (tile/quadkey aggregation) — the current client grid clustering is fine up to that point.

---

## E. Frontend

**How working apps do it:** every list has pull-to-refresh and pagination; every state (loading/empty/error) is designed; sign-in completes; no dead buttons; one design token source.

**Where Crave is:** the strongest area — real design system, React Query, debounced search, optimistic saves with rollback, good accessibility. Open items: OAuth wiring was fixed in code (needs the Supabase dashboard side: add `crave://` to the project's Auth redirect allowlist, and a device test); `ErrorState` component exists but is rendered nowhere, and stores/hooks swallow real errors into generic strings or nothing; `PlaceCardCompact` has no image fallback (blurhash forever); dead "Rate CRAVE"/"How CRAVE Works" buttons; static detail-screen skeleton vs animated feed skeleton; hardcoded token values in 4 components; no pull-to-refresh on Search/Saves; no `+not-found.tsx` route; `expo-location@^55` mismatched against the SDK-54 module set (likely build breakage); `com.anonymous.crave` bundle IDs and no `eas.json` (blocks store submission).

**What to do (rough order):** fix the Expo dependency mismatch first (`npx expo install --check` will catch it — it may literally be the Railway-adjacent "wait, the frontend doesn't build" surprise); wire `ErrorState` into the screens and stop swallowing errors; add the image fallback to `PlaceCardCompact` (copy `PlaceCard`'s); implement or hide the two dead buttons; add `RefreshControl` to Search/Saves and a `+not-found.tsx`; unify skeletons; sweep the 4 components onto design tokens; set real bundle identifiers + `eas.json` when ready for TestFlight/Play.

---

## F. Backend architecture cleanup

**How working apps do it:** one live implementation per concern; versioned API surface with one router convention; errors either handled meaningfully or propagated — never blanket-swallowed.

**Where Crave is:** two scoring engines (fixed — v4 now wired), two menu routes (fixed), two extraction pipelines (one dead), a queue worker system nothing enqueues to, `core/errors.py` empty, `app/api/routes/` existing solely to confuse, and blanket `except Exception: log-and-continue` across the entire pipeline layer — the pattern directly responsible for two of the worst silent failures found.

**What to do:**
1. Deletion pass (biggest single win): remove `app/pipeline/*`, the queue-based `run_worker_once` paths, `scoring/recompute.py`'s placeholder (after v4 is verified in prod), the deprecated `app/api/routes/menus.py`, `truth_engine.py`, and every module the extraction audit confirmed has zero live importers. Target: reading the repo tells the truth about what runs.
2. Replace blanket exception swallowing in pipeline stages with: catch → record to failure tracking (section B) → continue. Same control flow, but failures become visible.
3. Fold `app/api/routes/` into `app/api/v1/` so there is exactly one router convention.
4. Add ~10 integration tests around the seams that broke silently (menu serialize→schema round-trip, promotion chain writes a Place, scheduler jobs import successfully) — the specific class of bug this codebase produces is exactly what thin integration tests catch.

---

## G. Database & migrations

**Where Crave is:** migration graph is sound but had an unrebased branch point once already; `menu_snapshots` migration is authored but unapplied; model-vs-migration drift was found once, so assume more exists; production DB contents are unverified (and possibly empty/lost if SQLite was ever the fallback).

**What to do:** run `alembic upgrade head` in prod; then run a one-time `alembic check` / autogenerate diff against the live DB to surface any remaining model-vs-schema drift; adopt "migrations only on rebased branches" as a rule; take a look at what data actually exists in prod Postgres before assuming re-ingest scope.

---

## H. Ops, CI, and repo hygiene

**How working apps do it:** git push → CI (lint, typecheck, tests) → build → deploy, with config in the repo; secrets in the platform, never in files; the repo contains only source.

**Where Crave is:** zero CI, zero Docker/railway config in-repo, deploys are dashboard-manual; `requirements.txt` has impossible lower bounds (`starlette>=1.0.0`) and no ceilings — a strong candidate for the original crash; live secrets in `backend/.env`; a 49k-file cache dir with no gitignore entry; a committed-adjacent `venv/`; a forgotten git worktree duplicating the frontend.

**What to do:** pin `requirements.txt` to real, tested versions (this may *be* the Phase 0 crash fix); add a minimal GitHub Actions workflow (ruff + a compile-check + the section-F tests; `tsc --noEmit` for the frontend); commit a `railway.json`/Dockerfile so the deploy is reproducible; gitignore the cache dir; delete the stale worktree; keep secrets only in Railway.

---

## Suggested sequence (dependency-ordered)

| Phase | Work | Why this order |
|---|---|---|
| 0 | Read crash log → fix crash (likely requirements pins) → redeploy → migrate → health check + alerting | Nothing runs until this. |
| 1 | Security: JWT verification + Bearer tokens, close open endpoints, rotate secrets | Cheap, and the app should not take real users before it. |
| 2 | Verify menus end-to-end in prod; widen worker eligibility; capable extractor | The core product promise. |
| 3 | Schedule acquisition + ImageWorker; entity-matcher dedup; failure tracking + job_runs | Turns "hella scrapers" into a pipeline that runs itself. |
| 4 | Frontend punch list (Expo dep fix first) + device-test map & OAuth | Product feels finished. |
| 5 | Deletion pass + integration tests + CI | Locks in everything above; prevents regression to the orphan pattern. |

**Definition of "fully up and working":** production deploys green from CI; a new restaurant appears in the app without a human running a script; its menu, image, and score arrive within their job cadences; a signed-in user's saves are private to them; the map refreshes as you move it; and when any of that breaks, something pages you before two months pass.
