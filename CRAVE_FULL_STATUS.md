# CRAVE — Full Status Report

Everything done, everything found, every system graded, and the real path to
App Store ready. This supersedes the summaries in `CRAVE_ERROR_LOG.md` and
`CRAVE_REMEDIATION_PLAN.md` — those were earlier passes; this is the current
state of truth. `CRAVE_REMAINING_WORK.md` still holds the detailed
action-item list referenced below.

**Standing constraint on everything in this document:** no bash/shell access
existed at any point across this entire project — no `pip install`,
`npm install`, `alembic upgrade`, `pytest`, `tsc`, or `git` command was ever
run. Every fix below was written and hand-reviewed, never compiled or
executed. Treat "fixed" as "should be right," not "proven right," until you
run it yourself.

---

## 1. Everything done this session

### Security
- Real JWT verification (`app/core/user_auth.py`) replacing a straight-up
  IDOR — the backend used to trust whatever `user_id` a client sent, no
  check at all.
- CORS lockdown, security headers, docs/openapi hidden in prod, and a
  startup guard that now **refuses to boot in prod** with default secrets
  or wildcard CORS.
- Rate limiter rewritten — the old one had an off-by-one that let the first
  request in a fresh window through free every time; added an optional
  Redis-backed path for multi-instance deployments.
- Rate limiting applied to routes that had none (saves, hitlist, craves,
  share, image proxy) and API-key + rate-limit gating added to two fully
  public internal analytics routes that had neither.

### Ingestion / extraction
- Menu worker eligibility widened (was only attempting places with a
  website; now also tries Grubhub URL / menu source URL).
- A real extraction escalation stage added to the menu orchestrator as a
  fallback when the existing (already fairly capable) chain comes up empty.
- Image ingestion worker — fully built already, but only reachable through
  a manual loop nobody ran — is now actually scheduled (every 20 min).
- Naive exact-name-match deduplication replaced with real entity matching
  (name + address/domain/geo-proximity corroboration).
- Failure tracking added to the discovery/promotion pipeline: exponential
  backoff, dead-lettering after repeated failures, and a `job_runs` table +
  tracker so scheduled jobs are finally observable instead of one stdout
  line each.
- Google Places ingestion now detects `OVER_QUERY_LIMIT`/`REQUEST_DENIED`
  and stops instead of silently returning zero results forever (Google
  returns HTTP 200 even on quota errors — this was invisible before).
- Nominatim's non-compliant User-Agent fixed (their usage policy requires a
  real contact email/URL); confirmed the existing generic per-domain rate
  limiter already satisfies their request-rate policy.

### Map / Frontend
- Fixed a real app-crasher: the `expo-location` config plugin was missing
  from `app.json`, so the first location-permission request would crash
  the app on iOS (missing `NSLocationWhenInUseUsageDescription`).
- Fixed `expo-location` version mismatch (`^55.1.8` vs. what Expo SDK 54
  actually bundles, `~19.0.8`) plus several other expo-* patch mismatches.
- Fixed the OAuth redirect flow, dropped search query params, map viewport
  refetching + real clustering, and category/menu-availability fields that
  were previously hardcoded/wrong on the map.
- Fixed a genuine duplicate-render bug in `MapBottomSheet.tsx` (the tier
  name was rendered twice — once in the badge, once as plain text right
  below it).
- Fixed swallowed/generic error messages in the saves store — a user
  hitting the rate limiter or an expired session used to see the exact
  same message as a server crash, with no path out of the retry loop for
  an expired session specifically.
- Full punch list: image fallback for missing photos, dead "Rate CRAVE" /
  "How CRAVE Works" buttons, pull-to-refresh on search/hitlist, a missing
  `+not-found.tsx` 404 screen, and a design-token consistency sweep.

### Cleanup / Ops
- ~27 confirmed-dead backend files annotated as deprecated (not deleted —
  no git access to safely verify nothing breaks after removal).
- A genuinely impossible dependency pin fixed:
  `starlette>=1.0.0` in `requirements.txt` — starlette has never released a
  1.0, so this would make `pip install` fail outright.
- Added a CI workflow (syntax/import smoke test for backend, TS typecheck
  for frontend — no real test suite exists yet in either).
- Fixed `.gitignore` (a 49,000-file rendered-JS cache directory was never
  excluded).

---

## 1b. Correction — testing grade was wrong, now fixed

A follow-up spot-check (not by me — a re-verification pass against the
actual code) caught that this document's original "zero tests exist" claim
was **wrong**. `backend/tests/` has 20 real pytest files (~1,171 lines),
several genuinely substantive. I missed this earlier in the session because
a glob search for `backend/tests/**/*.py` returned nothing (a tool-usage
mistake on my part, not evidence the directory didn't exist) and I never
caught it. Owning that directly: the earlier "Testing — F" grade and the
CI comment claiming no tests exist were both false.

Since being caught, three things were fixed:
- `backend/tests/conftest.py` (new) — nothing in the app ever calls
  `Base.metadata.create_all()` (schema normally comes from Alembic against
  real Postgres), so a fresh SQLite file in CI would have had zero tables
  and every DB-touching test would have failed immediately with
  "no such table," independent of whether the test itself was correct.
  This creates the schema before tests run and points at a throwaway
  database instead of a real one.
- `.github/workflows/ci.yml` — now actually installs `requirements-dev.txt`
  (which is where `pytest` was declared, and wasn't being installed before)
  and runs `pytest -q`, instead of a commented-out step.
- `backend/tests/hitlist/test_hitlist_routes.py` — one test called
  `GET /hitlist/{user_id}`, a route this same session renamed to
  `GET /hitlist/me` (see the security fixes above). Updated the test to
  match. This is a direct, confirmed case of this session's own security
  fix breaking a pre-existing test — worth knowing about if other stale
  tests turn up too.

**Honest expectation, not a promise:** this is the first time
`backend/tests/` has ever been run against the current code — no shell
access existed anywhere in this project until this fix. Some of the other
19 files may surface real failures on the first CI run. That's the system
working as intended, not a sign the fix was wrong. Frontend still has zero
test files.

---

## 2. Fresh audit — new findings just found this pass

Two independent read-only audits were run against the current code
(post-fixes). These are **new** findings, not repeats of anything above.
One critical backend finding was independently spot-verified before
inclusion; the rest are as-reported and worth a quick human confirm.

### Backend — Critical
- **`app/services/query/proximity_query.py:64,74` — verified real.** Raw
  SQL uses `WHERE is_active = 1` against `Place.is_active`, which is a
  native Postgres `boolean` column in production. Postgres does not
  implicitly compare `boolean = integer` — this raises
  `operator does not exist: boolean = integer` at runtime. This function
  (`list_places_near`) is wired directly into `app/api/v1/routes/places.py`
  — it's the GPS-based "places near me" query, i.e. the main feed whenever
  a user opens the app with location on. This would 500 every time. Same
  pattern also in `app/services/data/target_selector.py:210` and
  `app/services/quality/data_quality.py:75` (lower-traffic ops scripts).

### Backend — High
- `app/services/truth/place_resolver.py:416-440` — constructs a `Place`
  with kwargs (`category_id`, `phone`) that don't exist on `Place.__init__`,
  which always raises `TypeError`, silently swallowed by a `logger.debug`
  call. This class isn't wired into anything live today, but it's a trap
  for whoever wires it in next.
- `app/services/aggregation/signal_aggregator.py` — computes rank/master
  scores with a formula that conflicts with the real, live scoring engine.
  Not imported anywhere today, but unlike the 27 already-annotated dead
  files, this one has **no** deprecation comment — reads as if it might be
  live. Should get the same annotation treatment.

### Backend — Medium
- Six completely empty (0-byte), unreferenced service files
  (`feed_service.py`, `map_service.py`, `place_detail_service.py`,
  `place_refresh_service.py`, `places_service.py`, `place_query_service.py`)
  plus `app/services/container.py` and `app/services/feed/feed_rank_adjuster.py`
  — all dead, none annotated, read as accidentally-truncated rather than
  intentionally retired.
- `app/api/v1/routes/enrichment.py` — the internal ops endpoints eager-load
  several relationships they don't actually use, adding unnecessary query
  overhead on every call.

### Backend — Low
- A fragile `hasattr()`-on-class pattern in `place_resolver.py` that
  happens to work today but would silently no-op if a column is renamed.
- The codebase has a lot of `except Exception: pass` blocks (39 files) —
  spot-checked a sample and they look intentional, but it's a dense enough
  pattern that a real error could hide in a careless copy-paste later.

### Frontend — Critical
- `app/(tabs)/map.tsx` — `loadFeatures` has no request sequencing. The
  initial-mount fetch and the follow-up fetch once location resolves can
  race; if the slower one lands second, it silently overwrites the correct
  viewport's markers with stale ones, with no way to detect it happened.
- `app/place/[id].tsx` — the menu-fetch effect has no mounted-check or
  cancellation. Fast back-and-forth navigation between two place pages can
  let an older response land after a newer one and overwrite the wrong
  place's menu data, or set state after the component's already unmounted.

### Frontend — High
- `src/components/AuthSheet.tsx` — if the OAuth redirect comes back without
  valid tokens, the sign-in sheet just quietly stops (spinner clears, no
  toast, no error) — a real sign-in failure gives zero user feedback.
- `app/(tabs)/more.tsx` — Sign Out calls an async function without
  awaiting or catching it. If it fails offline, it's an unhandled promise
  rejection with no user-visible feedback.
- `app/place/[id].tsx` — the Directions button uses falsy checks
  (`!place.lat`) instead of null checks, so a place exactly at latitude or
  longitude `0` silently loses its Directions button (a real edge case, not
  just theoretical, near the equator/prime meridian).

### Frontend — Medium
- `src/stores/authStore.ts` — one `console.warn` isn't gated by `__DEV__`
  like every other log call in the codebase — ships internal error detail
  to production console.
- `src/stores/authStore.ts` — an auth-state-change subscription is never
  unsubscribed; latent today (only initialized once), but a future
  re-invocation would stack duplicate listeners.
- `app/(tabs)/index.tsx` — there's a window where neither the selected city
  nor GPS location has resolved yet, during which the home feed fetches
  completely unscoped (no city, no coordinates) with no loading indicator
  explaining why filters are missing.
- Map markers have no `accessibilityLabel` — screen reader users get no
  place-name announcement on the map, inconsistent with the rest of the app.

### Frontend — Low
- Two exported-but-unused `@deprecated` functions in `scoring.ts` that
  duplicate live logic with drifted copy.
- The "Rate CRAVE" disabled row doesn't set
  `accessibilityState={{ disabled: true }}`, so VoiceOver still announces
  it as tappable even though it isn't.

---

## 3. System-by-system grades

| System | Grade | Why |
|---|---|---|
| Security | B | Real auth/authorization now exists where there was none; still capped by secrets not yet rotated/set in the real prod environment. |
| Menu extraction | B- | Genuinely more capable than it looks (provider detection, hydration fallback, live Grubhub fetch, new escalation stage), but real-world coverage is unverifiable without production DB access. |
| Images | B+ | Real Google Places photo pipeline with a proper server-side proxy that keeps the API key off the client (checked specifically, done correctly) — main gap was scheduling, now fixed. |
| Map | **C+** (down from B) | Real clustering and viewport-aware fetching, but `loadFeatures` in `map.tsx` has no abort/mounted-ref guard — the race-condition finding above is real and still unfixed. |
| Auth | B+ | Real Supabase OAuth + JWT verification, session persistence correctly configured; one real gap found this pass (silent failure on bad redirect). |
| Hitlist / Saves | B | Backend-synced, optimistic, now with real differentiated error messages instead of two generic strings. |
| User-generated content (photo/video upload) | **F — doesn't exist** | Zero upload capability anywhere in the app. Not a bug; an unbuilt feature. |
| UX | B- | Good bones (haptics, accessibility labels, a real point-of-view via the tier system); onboarding is one Alert dialog, no skeleton loading states, no way to correct a mismatched Crave. |
| UI | B | Consistent dark theme and a real design-token system, now more consistently followed; visually coherent but light on empty-state/loading polish. |
| Ops / Deployability | C+ | Solid job design and now-real observability, but the grade is capped hard by the fact that production itself has been down for two months. |
| Testing | **D+** (up from F — see section 1b) | Backend has 20 real test files; some substantive, some empty stubs. Now actually wired into CI with schema creation, one known stale test fixed. Frontend: zero test files. Still unverified by execution beyond this correction pass. |

**Overall project grade: C+, unchanged.** Gated by the same three things
regardless of the testing correction: the `proximity_query.py` boolean bug
(confirmed real, confirmed still unfixed, hits the main GPS feed) is the
one thing most likely to break production on day one; test execution in CI
is now real but still unproven against the live app; and deploy status
remains unverified. The individual systems are mostly B-range — built with
real care, not slapped together — but a gate is a gate, not an average.

---

## 4. What's completely missing (not broken — absent)

- Photo/video upload for users.
- Any form of reviews, ratings from users, or comments.
- Push notifications ("Coming soon" placeholder only).
- A real onboarding flow (currently a single Alert dialog).
- Automated tests on the frontend (backend has real ones — see section 1b).
- Error/crash monitoring in production (no Sentry or equivalent).
- A marketing/landing website — `crave.app/privacy` and `crave.app/terms`
  are linked from the app but nothing in this repo builds them; unclear if
  they resolve to real pages.

---

## 5. The real path to 100% / App Store ready

**Percent complete, honestly: ~60% of the way to submission-ready, ~65-70%
of the way to what most people would call "A-grade" engineering.** Those
differ because App Store readiness includes a bunch of non-code work
(developer accounts, store assets, live legal pages) that has nothing to
do with code quality.

### Deploy blockers (do these first, nothing else matters until this works)
1. Read the actual Railway crash log — the real root cause has never been
   seen this entire project.
2. **Fix the new critical `proximity_query.py` bug** — this may well be
   part of why things break, if location-based feed requests have ever
   hit this in production.
3. Set `SUPABASE_JWT_SECRET` and a real `SECRET_KEY` — the app now
   deliberately refuses to boot in prod without them.
4. Rotate every secret currently sitting in plaintext in `.env`.
5. Confirm `DATABASE_URL` points at a real, live Postgres instance.
6. Run `alembic upgrade head` — two migrations have never touched a real
   database.

### Before shipping the frontend
7. `npm install` to un-stale `node_modules` and regenerate
   `package-lock.json`.
8. A full native rebuild (not a JS update) — required for the location
   permission fix and plugin to take effect.
9. Fix the two new critical frontend findings (map race condition, menu
   fetch race condition) — both produce silently wrong data, which is
   worse than an obvious crash.
10. Run `npx expo-doctor` to confirm the `react-native-worklets` version
    pairing with Reanimated.
11. Run `npx tsc --noEmit` — nothing here has ever been compiled.

### For App Store submission specifically
12. Apple Developer ($99/yr) + Google Play Console ($25 one-time) accounts.
13. Live, real privacy policy and terms pages.
14. App icons + store screenshots, all required sizes.
15. Apple's privacy "nutrition label" (location + auth/email disclosure).
16. A TestFlight round on a real device before public release — this app
    has never run on real hardware.

### To actually reach "A" /90%+
17. Run the backend suite for real and fix what it surfaces (expect some
    failures on first run — see section 1b), fill in the empty stub test
    files, and add a frontend test suite from zero.
18. Error monitoring (Sentry or equivalent) in production.
19. A stretch of stable, crash-free production uptime — code review isn't
    proof, running is.
20. Decide on and either build or explicitly defer: user photo/video
    uploads, push notifications, a real onboarding flow.

---

## 6. What I still cannot do myself

No shell access existed anywhere in this project — I can't run `npm
install`, `pip install`, `alembic upgrade`, `pytest`, `tsc`, a native build,
or any `git`/deploy command. Every item in section 5 above that involves
"run" or "install" needs to happen on your machine or in CI. Full
line-by-line detail on every open item is in `CRAVE_REMAINING_WORK.md`.
