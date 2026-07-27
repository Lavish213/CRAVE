# CRAVE — Project Timeline & Grades

*Based on actual git commit history (not assumed) — the build happened Apr 13–20, 2026,
then the repo sat untouched for ~3 months until this session (Jul 27).*

## Phase-by-phase

| Phase | Dates | What happened | Grade |
|---|---|---|---|
| 1. Backend bootstrap | Apr 13 | Clone, initial backend build, Grubhub pipeline, env security cleanup | B — standard early scaffolding, clean commits |
| 2. Production hardening + V4 scoring | Apr 13–18 | Schema fixes, candidate promotion pipeline, V4 5-bucket scoring engine, blog ingestion, risk/consensus system | B+ — real architectural investment, iterated fast |
| 3. Frontend build-out | Apr 18–19 | Full Expo/React Native app: design tokens, map, hitlist, search, auth (Supabase), 20+ focused polish commits | A- — genuinely thorough, good commit discipline (small, single-purpose commits with clear messages) |
| 4. Deploy + last hardening | Apr 19–20 | Railway deploy config, Postgres fixes, "repair all broken data contracts (map, search, menu, city init)" | B — reached a real milestone (`de5990c8`), but that commit message itself admits multiple systems were broken and needed repair |
| 5. Dormancy | Apr 20 – Jul 26 | Nothing committed for ~3 months, but local work kept happening in a second uncommitted/unsynced clone (food-backend-v2) | F — this is the root cause of everything that went wrong later |
| 6. Recovery (this session) | Jul 27 | Fixed broken env, found & fixed a live map bug, discovered + merged 100+ files of at-risk uncommitted work, caught a credential near-leak, fixed a duplicate-migration bug, rewrote a stale test file, got both backend (132/132) and frontend fully green | B+ for the recovery itself — but see below |

## What got done today

- Diagnosed and fixed local dev env: venv activation, wrong-directory commands, missing `boto3`/`pdfminer` deps, pytest `sys.path` bug (added `pythonpath = .` to `pytest.ini`), stale SQLite schema (ran `alembic upgrade head` after wipe).
- Found & fixed a real bug: `map_query.py` had silently lost its bounding-box radius filter — `/map` was ignoring location entirely. Restored from CRAVE's version, wired up the missing `/map/geojson` endpoint.
- Discovered CRAVE and food-backend-v2 (two local clones of the same GitHub repo) had diverged hard — 100+ files of uncommitted work sitting only in CRAVE's working tree (visibility system, truth-stabilization schema, Redis cache, JWT auth, job-run tracking, image classifier, v3/v4 scoring). Merged both directions and pushed a unified history to `origin/main`.
- Caught and prevented a credential leak: a `.gitignore` auto-merge briefly dropped the Grubhub-credentials exclusion; `.grubhub_env` was one `git add -A` away from being committed. Fixed before commit, verified with `git log --stat | grep grubhub` (clean).
- Found and fixed a duplicate-migration bug (`menu_snapshots` created by two independent migration chains) — made idempotent so it doesn't break for anyone cloning fresh.
- Rewrote a fully stale test file (`test_website_provider_probe.py`) that tested a scoring model (confidence tiers, clover.com as valid provider) the code had since moved past (score/100 scale, clover hard-blocked).
- Fixed frontend: disk space, clean `npm install`, `tsc --noEmit` now passes with 0 errors (was 73).

## Grades
| Area | Before | Now |
|---|---|---|
| Backend tests | Broken (5 collection errors, couldn't even run) | 132 passed, 0 failed, 11 skipped (need seed data) |
| Frontend build | Broken (ENOSPC, 73 TS errors) | Clean |
| Repo state | Two silently-diverging clones, huge uncommitted work at risk | Converged, pushed, backed up |
| Security hygiene | Near-miss credential leak | Fixed, verified clean |
| **Overall (this session)** | **D** (nothing ran, real feature broken, work at risk of loss) | **C+** (solid architecture, real feature depth, but process gaps are the risk now — see below) |
| **Overall (whole project, Apr → now)** | — | **C** — the engineering itself (scoring engine, frontend polish, auth, deploy config) is B/B+ work. The grade is dragged down by process: 3 months of uncommitted local drift, two clones silently diverging, and a credential-exclusion rule that almost got lost in the merge. Code quality isn't the risk here — losing work or leaking secrets is. |

## What's left — App Store / production readiness
Not yet touched this session, roughly in priority order:

1. **Seed data for tests** — 11 skipped tests all skip on "no active places in DB." Run one of the existing `backend/app/scripts/seed_*.py` or add a pytest fixture inserting a minimal place, so trending/signals are actually exercised.
2. **Production config audit** — confirm `SECRET_KEY`, `SUPABASE_JWT_SECRET`, `CORS_ALLOW_ORIGINS`, `DATABASE_URL` (should be Postgres, not SQLite) are all properly set wherever this deploys (Railway config already exists in the repo — verify it's current).
3. **No error monitoring found** — no Sentry/crash-reporting wired up anywhere I saw. Needed before shipping so production crashes aren't invisible.
4. **`npm audit`** — 24 vulnerabilities (2 critical, 8 high) in frontend deps, unreviewed.
5. **CI verification** — `.github/workflows/ci.yml` just landed via this merge; confirm it's actually green on GitHub after the huge push, not just assumed.
6. **App Store submission mechanics** — none of this was addressed: app icons/screenshots, App Store Connect listing, privacy policy URL, permission-usage strings (location, camera for uploads), TestFlight build, EAS/Expo build config, age rating, actual on-device testing (only checked type errors, not runtime behavior).
7. **Dead code cleanup** — `map_service.py` in both repos is confirmed-unused duplicate code, safe to delete.
8. **Process fix, not code fix** — the root cause of most of this session's fires was uncommitted work piling up silently across two clones. Worth adopting: commit at the end of every work session, and/or a pre-push hook that runs `pytest` so broken state can't get pushed unnoticed.

Both `CRAVE` and `food-backend-v2` are at commit `c66d34b` on `origin/main` as of this summary.

---

## Full Audit (2026-07-27)

Five-part audit: security/secrets, prod config, backend code quality, test/dependency coverage, frontend. Read-only — nothing below was auto-fixed.

### Do this first — before anything else
1. **Rotate credentials.** `backend/.env` (working tree, not committed under current `.gitignore`) holds a live Supabase service-role key, Google Places API key, and a live Grubhub session cookie in plaintext. `.gitignore` protects it *now*, but CRAVE's own git history has a commit titled "remove env files from tracking" — meaning `.env` *was* tracked at some point early on. Run `git log --all --full-history -- backend/.env` in both repos to see if real values were ever committed. If they were, rotate them regardless of whether they're still reachable in history — don't assume "removed from tracking" means "safe."
2. **Silent prod DB fallback.** `settings.py` returns a SQLite path unconditionally if `DATABASE_URL` is unset, and `_validate_prod_config()` in `main.py` never checks `database_url` at all. A Railway deploy that's missing the `DATABASE_URL` env var would boot successfully and silently run on ephemeral local SQLite — a data-loss trap that gives zero warning. Add `database_url` to the prod validation check.
3. **`API_KEY` has the same gap.** `_validate_prod_config()` doesn't check it either — if unset in prod, `require_api_key` (`auth.py`) opens up to everyone with no startup error.
4. **No rate limit on `/signals/intake`** (`signals.py`) — every other write endpoint has one, this doesn't. Abuse/cost exposure on a public-facing intake route.
5. **No React error boundary anywhere in the frontend.** One bad crash currently white-screens the whole app with no recovery UI. `frontend/app/_layout.tsx` is where this belongs.

### Real but lower-urgency
- **Two "covered" tests are empty files.** `backend/tests/test_promotion_pipeline_v2.py` and `test_truth_resolver_v2.py` are 0 bytes — the discovery-pipeline-v2 system (promotion gate, truth resolution, AOI expansion) has *zero* real coverage despite looking tested in a directory listing.
- **Three different "master score" algorithms exist** (`recompute.py`, `place_normalizer.py`, and an orphaned `scoring/master_score.py`), only two of which anything actually calls. Six files in `services/scoring/` (`place_score_v3.py`, `score_place_v2.py`, `score_all_places_v2.py`, `master_score.py`, `rank_score.py`, `compute_master_score.py`) are dead — nothing imports them outside themselves. Worth consolidating before a change gets made to the wrong one.
- **Frontend `localhost:8000` fallback has no build-time guard** — a misconfigured EAS build profile could ship to the App Store silently pointing at localhost. Same root issue as backend's fallback pattern in #2.
- **CI (`.github/workflows/ci.yml`)** runs real backend tests but its own comments admit the frontend `npm ci` step wasn't verified working when added — confirm on GitHub Actions it's actually green now that `package-lock.json` is regenerated.
- **Coverage gaps with literally zero tests:** menu extraction (~107 files, 1 test file), the upload/image pipeline, Redis caching, JWT auth (`user_auth.py`), job-run tracking, and scoring v4. No `pytest-cov` configured, so there's no way to measure this quantitatively — only pass/fail counts.
- **Frontend has zero automated tests** — no test files, no `"test"` script in `package.json`.
- **`app.json` bundle identifier is still the Expo default** `com.anonymous.crave` — must be a real registered identifier before App Store submission.
- `conftest.py` sets up the DB schema but no shared fixtures — three different ad-hoc DB-access patterns coexist across test files.

### Confirmed OK (checked, no action needed)
`.gitignore` correctly excludes credentials now · CORS fails closed and hard-fails prod on `*` · JWT auth is properly implemented and gated · no SQL-injection risk in any request-handling path · no path-traversal risk in R2 upload keys · no bare `except:`, no stray `print()`, all 22 DB models properly registered · `/health` does a real DB connectivity check, not a stub · frontend has no hardcoded secrets · frontend error/retry UI is actually consistent across screens · location-permission justification string present · privacy policy and terms links exist in the app.

*(`npm audit` for the frontend's flagged CVEs still couldn't be run — the sandbox's bash tool has been unavailable all session due to a disk-space error on its side. Run `cd frontend && npm audit` yourself when convenient.)*

---

## Test backlog — everything with zero real coverage

Priority order:

1. **`app/core/user_auth.py`** — JWT verification, the dev-bypass gating, expired/malformed token handling. Zero tests on the auth boundary itself is the highest-priority gap.
2. **Regression test for `_validate_prod_config()`** — assert it actually raises when `database_url`/`API_KEY` are unset in prod. This directly closes the two CRITICAL config gaps found in the audit and stops them from silently regressing again.
3. **`services/scoring/place_score_v4.py`** — this is the *live* scoring path (wired to the scheduler/worker); it has zero tests, while the *dead* `place_score_v3.py` is the one that's tested. Worth testing the module that's actually running.
4. **Discovery pipeline v2** — `test_promotion_pipeline_v2.py` and `test_truth_resolver_v2.py` exist but are empty (0 bytes). Needs real tests for `promotion_gate_v2.py`, `promote_service_v2.py`, `promotion_orchestrator_v2.py`, `aoi_grid_scanner.py`, `candidate_store_v2.py`.
5. **Upload/image pipeline** — `upload_service.py`, `r2_client.py`, `image_url_builder.py`, `utils/image_pipeline.py`, `workers/image_processing_worker.py`, and everything in `services/images/` (dedup, EXIF, classifier, visibility_assigner, ranker, selector) — 0 tests across all of it.
6. **Redis caching layer** — `redis_client.py`, `response_cache.py`, `cache_helpers.py`, `cache_keys.py`, `cache_ttl.py` — 0 tests.
7. **Job run tracking** — `job_run_tracker.py`, the `JobRun` model, `ingest_runner.py`, `aoi_scan_job_runner.py` — 0 tests.
8. **Menu extraction** — biggest surface area (~107 files), only `test_website_provider_probe.py` exists. Provider extractors (Toast, Square, Chownow, Popmenu, Olo, Grubhub) and `menu_extraction_router.py` are all untested. Lowest priority to *start* despite size, since it's scraping/parsing logic that changes with provider HTML — write these last, and expect to maintain them often.
9. **Frontend — everything.** No test runner is even configured (no `"test"` script in `package.json`, no test files anywhere). Before writing tests, first decision needed: Jest + React Native Testing Library is the standard Expo choice — install and configure that first, then start with the API client layer (`src/api/*.ts`) since it's pure logic and easiest to test in isolation.

Also needed but infrastructure, not individual tests: add `pytest-cov` so coverage can be measured by %, not just pass/fail counts — right now there's no way to know how deep any of this actually goes.
