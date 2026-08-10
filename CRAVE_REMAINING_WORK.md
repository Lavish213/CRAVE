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

## 2026-08-05 — project-grade systems review (branch `claude/project-grade-systems-review-4ot7d0`)

Unlike the log above, every fix in this section was written, then actually
run: full backend pytest suite (445 passing) and `npx tsc --noEmit` (clean)
after each change, on a real checkout with shell access. Earlier in this
same session (prior to this log entry) the scheduler was split out of the
web process, a missing DB index was added for the map bounding-box query,
frontend preload/prefetch was added for map + feed, and ImageWorker's
place-selection fairness bug was found and fixed. This entry covers the
follow-up pass: hunting down every other instance of the same two bug
classes elsewhere in the codebase.

### Backend: menu_worker.py had the identical starvation bug as image_worker.py

`app/services/workers/menu_worker.py::_load_places_requiring_menu` ordered
strictly `rank_score DESC, id ASC` with a plain `LIMIT BATCH_SIZE` (25) and
no rotation — the exact shape the module's own docstring already warned
about, confirmed in production for the identical pattern in
`image_worker.py` (Lodi's 48 places sat at zero images across 622
consecutive runs). The backoff mechanism already in this file
(`_not_in_backoff_clause`) only protects against a *repeat-failing* place
hogging every run — it does nothing for a place with a valid menu source
that's simply never been attempted and has a low `rank_score`, since
discovery keeps refilling the top of that ordering with newer, higher-
signal places ahead of it.

Fixed by mirroring `image_worker.py::_select_places`'s pattern: reserve
`max(1, BATCH_SIZE // 5)` (5) slots of each batch for the oldest eligible
places by `created_at`, on top of the rank_score-priority slice, sharing all
the same filters (website/grubhub/menu_source_url present, no existing menu
`PlaceTruth` row, not in backoff). New test:
`backend/tests/test_menu_worker_starvation.py`, mirroring
`test_image_worker_starvation.py`'s shape (80 high-rank + 5 low-rank places,
assert at least one low-rank place survives the batch selection).

### Frontend: the same unguarded stale-response race existed in four more places

Same bug class already fixed this session in `map.tsx` and `add-spot.tsx`:
a `.then()` handler calling `setState` unconditionally, with no check that
the screen's identity (place id, signed-in account, or selected city) is
still the one the request was made for. A background research agent
audited every other data-fetching screen/hook first (Feed and Search are
safe — React Query's per-key caching means a stale response resolves into
its own now-irrelevant cache bucket rather than overwriting the current
one; `useLocation` is safe — a single shared promise means there's only
ever one in-flight response, period). Confirmed and fixed:

- **`app/place/[id].tsx`** — the menu fetch (`getPlaceMenu` →
  `setMenuItems`/`setMenuVerifiedAt`) and the craves-for-place fetch
  (`getCravesForPlace` → `setCraves`) were both keyed only on `id` with no
  guard. Since expo-router can reuse this screen instance across an `id`
  change (e.g. tapping from one place's menu/social content into another
  place's detail) rather than unmounting, a slow response for the old place
  could resolve after the new place's and silently repaint the screen with
  the wrong place's menu/craves. Fixed with two independent generation
  refs (`menuGenerationRef`, `cravesGenerationRef` — kept separate since
  they're unrelated requests; a shared counter would make each falsely
  invalidate the other on mount).

- **`app/(tabs)/craves.tsx` + `src/stores/cravesStore.ts`** —
  account-switch version of the same bug. Neither `getCraveItems()` nor
  `getMyPlaceSaves()` takes a userId (both rely on the ambient auth token),
  so a slow request in flight when the signed-in account changes could
  resolve after the new account's and overwrite `craves`/`placeSaves`/the
  persisted `saves` store with the previous user's data. Fixed with an
  `accountGenerationRef` in craves.tsx (bumped on `user?.id` change, same
  pattern as `add-spot.tsx`'s `accountGenerationRef`) guarding
  `loadCraves`/`loadPlaceSaves`, and a module-level `_loadSequence` counter
  in `cravesStore.ts` guarding `loadSaves` (same shape as that file's
  existing `_pendingSaves` module-level guard).

- **`src/hooks/useTrending.ts`** — city-switch version. `load()` had no
  guard against a city switch mid-request; switching city A → B quickly
  with A's `fetchTrending` resolving after B's would clobber the correctly-
  displayed city-B trending list with stale city-A data. Fixed with a
  `latestRequestCityRef`, set synchronously at the start of `load()` before
  the async call, checked before `setTrending`/clearing `refreshing`. The
  `cache[cityId] = data` write stays unconditional — still correct for a
  future switch back to that city even when it's not the one on screen.

- **`app/rank/[placeId].tsx`** — found during a follow-up sweep for any
  remaining unguarded `.then()` chains in effects keyed on a route param.
  Same shape as `place/[id].tsx`: `fetchPlaceDetail(placeId)` had no guard
  against a `placeId` change reusing the screen instance. Lower severity
  than the others here — the actual ranking calls (`startRanking`,
  `submitComparison`) key off the route's `placeId` directly, not this
  `place` state, so an unguarded race here could only have caused a
  momentary wrong name/image in stage 1, never corrupted ranking data.
  Fixed the same way regardless, with a `placeGenerationRef`.

### Verification

- `cd backend && rm -f test_crave.db && python -m pytest -q` — 445 passed
  (444 baseline + 1 new test).
- `cd frontend && npx tsc --noEmit -p .` — clean, no errors.

### Follow-up — CodeRabbit's second review pass on PR #40 found 3 more real issues in the above

Correction to this log's own claim above: `rank/[placeId].tsx`'s race was
**not** harmless. CodeRabbit correctly pointed out that between a `placeId`
change and the new place's fetch resolving, the old `place` state stayed on
screen — so the user could see place A's name/image while `handlePickTier`/
`handleChoose` recorded a ranking against the route's (new) `placeId`, a
real risk of ranking the wrong-looking place, not just a cosmetic flash.
Fixed by resetting `place`/`error`/the whole ranking-flow state (`opponent`,
`stage`, `tier`, `token`, `result`, `round`, `beatOpponentName`) at the start
of the `placeId`-change effect, and gating the loading screen on
`place.id === placeId` rather than just `!place`.

Two more, both confirmed and fixed:

- **`useTrending.ts`** — the `latestRequestCityRef` guard tracked only
  `cityId`, so two overlapping requests for the *same* city (e.g. `refresh()`
  fired twice quickly) both passed the check, meaning a slower of two
  same-city responses could still overwrite a newer one, and a cache-hit
  load never cleared `refreshing`, so it could stay stuck `true` from an
  earlier in-flight network call. Replaced with a monotonically increasing
  `latestRequestRef` sequence number, incremented on every load (cached or
  network), and the cache-hit path now explicitly clears `refreshing`.

- **`test_menu_worker_starvation.py`** — `_load_places_requiring_menu` has
  no city filter (it selects eligible places across the whole table by
  design), so the test's fairness-slice assertion could flake if another
  test left behind an eligible row with an older `created_at` than the
  test's own low-rank places, silently displacing them from the reserved
  slice. Fixed by pinning explicit `created_at` timestamps (`Place.__init__`
  doesn't accept `created_at` — it's set as a post-construction attribute)
  so the test's low-rank places are deterministically the oldest rows in
  the table regardless of execution order or other tests' leftover data.

Verified again: 445 backend tests passing, `tsc --noEmit` clean.

### Follow-up — live verification pass, 3 more residual gaps found and closed

Asked to actually run the app and check the fixed screens, not just trust
typecheck/tests. Backend booted cleanly against a fresh SQLite DB (Alembic
migrations + a seeded place, confirmed via `GET /api/v1/place/{id}`).
Full-app Playwright screenshots hit two pre-existing platform gaps unrelated
to anything touched this session: `react-native-maps` has no web-target
support (Metro's web bundler chokes on its native codegen import), and a
`zustand` transitive dependency emits `import.meta`, which Metro's
non-module web bundle can't execute. Neither was worth patching around
further just for a smoke test.

Pivoted to differential Jest/React-Testing-Library tests instead — write a
test against the fixed code, confirm it passes, then swap in the pre-fix
version of the same file and confirm the test fails exactly as predicted,
then restore the fix. This is more rigorous than a screenshot for
timing-dependent bugs, since a static render can't prove a race is actually
closed. `useTrending.ts`'s round-2 fix passed this differential check
cleanly. But applying the same test to `rank/[placeId].tsx`, `place/[id].tsx`,
and `craves.tsx`/`cravesStore.ts` surfaced a narrower, real class of bug the
generation-ref/sequence guards didn't cover:

**The guards stop an out-of-order OLD response from overwriting a NEWER
one — they don't clear the *currently displayed* stale data the moment the
identity (place id or account) changes.** Wherever a section's visibility
isn't gated by its own loading flag, the previous place's/account's data
stays on screen for as long as the new fetch is in flight:

- `place/[id].tsx` — the "Seen on social" (craves-for-place) section had no
  loading flag, just `craves.length > 0`. Navigating from place A to place
  B kept showing place A's crave rows — each a real tap target to
  `matched_place_id` — until B's fetch resolved. Fixed by resetting
  `craves` to `[]` at the start of the effect (the menu section right above
  it didn't need this — it already has a `menuLoading` flag that gates its
  visibility regardless of what's still in `menuItems`).
- `craves.tsx` — the "Added" (`placeSaves`) section had the same shape.
  Fixed by resetting `craves`/`placeSaves` inside the existing
  `accountGenerationRef` effect (keyed on `user?.id`, so it only fires on a
  genuine account change — never on pull-to-refresh or right after sharing
  a link for the same account, so no new empty-flash regression).
- `cravesStore.ts` — the main Saves list *does* have a `loading` flag, but
  craves.tsx's skeleton only renders when `loading && saves.length === 0`,
  so a non-empty stale list from a previous account was never hidden just
  because a fetch for a *different* account was in flight. Fixed with a
  `_lastLoadedUserId` marker (mirroring this file's existing module-level
  guards like `_pendingSaves`) — clears `saves` only on a genuine account
  mismatch, deliberately preserving both a same-account refresh (must keep
  showing cached data while it revalidates) and a legitimate same-account
  app restart (AsyncStorage-persisted saves should show immediately, not
  flash empty just because the marker isn't known yet after rehydration).

`rank/[placeId].tsx`'s round-2 fix (the CodeRabbit-flagged Major
data-integrity issue) passed its differential test cleanly with no further
gaps found — its reset was already complete because it clears every piece
of ranking-flow state up front, not just the visible one.

Verified: 445 backend tests passing, 78 frontend tests passing,
`tsc --noEmit` clean. All differential/scratch test files were deleted
after verification — they existed only to prove each fix, not as
permanent coverage.

### Follow-up — a real bug the live-verification pass actually found, and 3 more CodeRabbit findings on cravesStore.ts

While live-verifying the Feed screen against a seeded database, it rendered
completely empty despite the API reporting `total: 2`. Root cause turned
out to be two layered issues: the immediate one was a mistake in the test
seed data (`rank_score` set to `90.0`/`80.0` instead of the schema's
required `0.0`-`1.0` normalized range) — but that only mattered because
`GET /api/v1/places` (`backend/app/api/v1/routes/places.py`) was silently
swallowing the resulting per-place `PlaceOut` validation failure at
`logger.debug`, invisible at the app's default log level. In production,
*any* place whose data ever fails validation for any reason vanishes from
every feed response with zero operational visibility, while `total` (from
the raw query, computed earlier) keeps counting it like nothing's wrong.
Bumped to `logger.warning` so this is actually visible when it happens for
real.

CodeRabbit's review of that same commit then found 3 more real gaps in the
`savesUserId` design from the entry above — all confirmed with differential
tests (fail on the pre-fix version, pass on the fix):

- `loadSaves()` cleared `saves` but left `savesUserId` pointing at the old
  account until the fetch succeeded. An optimistic `addSave`/`removeSave`
  for the new account landing in that window would persist under the wrong
  owner label — if the app died right then, the *old* account could sign
  back in later and see the *new* account's data. Fixed by setting
  `saves`+`savesUserId` atomically in the same `set()` call.
- `addSave`/`removeSave` had no generation guard at all. `removeSave`'s
  failure-path rollback restored `prev` — the pre-removal account's full
  list, captured at call time — even after `clearSaves()` had already run
  for a sign-out, so a slow DELETE failing after sign-out could repopulate
  the signed-out account's data. Added a separate `_accountGeneration`
  counter (not reusing `_loadSequence`, which bumps on every `loadSaves()`
  call including harmless same-account refreshes) that only changes on a
  real account switch; both mutations check it before their post-await
  state updates. `_pendingSaves` (keyed only by `place.id`, no account
  scoping) is now cleared on every account switch too, since a still-in-
  flight add from the old account could otherwise silently block the new
  account from saving that same place.
- zustand's `persist` middleware rehydrates from `AsyncStorage`
  asynchronously — there's a real window right after the store is created
  where `saves`/`savesUserId` still read as their pre-hydration defaults,
  not the previous session's actual persisted values. `loadSaves()` now
  awaits `useCravesStore.persist.hasHydrated()`/`onFinishHydration()`
  before reading or writing anything, so it can't make its clear-or-not
  decision against stale defaults, and zustand's own rehydration `set()`
  can never land later and silently revert an already-fresher fetch
  result.

Verified: 445 backend tests, 78 frontend tests, `tsc --noEmit` clean.

### Follow-up — CodeRabbit round-3 on `cravesStore.ts`: 3 more real gaps in the same file, all fixed with regression tests

CodeRabbit's review of the previous entry's own commit found 3 more real
issues in `cravesStore.ts`, all confirmed with new differential tests in
`cravesStore.test.ts` (fail against the pre-fix version restored from git,
pass against the fix):

- `loadSaves()` still created its `_loadSequence` token (`mySequence`)
  *after* `await _waitForHydration()`, not before. A `clearSaves()`
  (sign-out) that ran while hydration was still pending would bump
  `_loadSequence` during that window, but since `mySequence` was only read
  once hydration finished — after the bump — it read the *post-clearSaves*
  value and matched trivially. The call would proceed exactly as if
  sign-out had never happened, fetching and applying the just-signed-out
  account's saves. Fixed by capturing `mySequence` before the hydration
  await (so a bump during that window is visible as a real mismatch) and
  adding an early return right after the await.
- `addSave`/`removeSave` guarded against a stale *account* via
  `_accountGeneration`, but not a stale *overlapping mutation for the same
  place*. Concretely for `removeSave`: two overlapping calls for the same
  place (e.g. a stale pre-account-switch call and a fresh post-switch call,
  or any other overlap) meant the older call's failure-path rollback could
  restore its captured `prev` — the pre-removal list — after a newer call
  for the same place had already succeeded in removing it, silently
  undoing the correct, newer removal. `addSave`'s analogous `finally` had
  the same shape: an older call's cleanup could delete a newer call's still
  in-flight `_pendingSaves` marker. Fixed with a per-`placeId` monotonic
  mutation token (`_saveMutationToken`, a `Map<string, number>`) —
  `addSave`/`removeSave` each capture their own token at call start, and
  only clear the pending marker / apply the rollback if their token is
  still the current one for that `placeId`.
- `_waitForHydration()` only ever resolved via zustand persist's
  `onFinishHydration` listeners — reading zustand's own `persist.ts`
  directly confirmed those listeners fire only on a *successful*
  rehydration; an `AsyncStorage.getItem` rejection runs the middleware's
  separate `.catch()` path instead, which only calls `onRehydrateStorage`'s
  error callback and never touches `finishHydrationListeners` or
  `hasHydrated`. A real storage failure (corruption, quota, whatever) would
  leave any `loadSaves()` call already waiting on hydration stuck forever.
  Fixed by wiring `onRehydrateStorage`'s error callback to a module-level
  `_hydrationFailed` flag plus a small waiter-list, so a storage failure
  now degrades to "proceed with in-memory defaults" instead of hanging.

New test file `cravesStore.test.ts` (previous rounds' differential tests
were scratch-only and deleted after verification — this one is kept as
permanent coverage since these are exactly the kind of timing bugs a static
render/typecheck can't catch): mocks `@react-native-async-storage/async-
storage`'s `getItem` with a manually-resolvable/rejectable promise to
control hydration timing precisely, and `../api/saves` to control
fetch/create/delete timing. 4 tests: clearSaves-during-hydration-wait,
normal-load-still-works (regression guard for the token-reordering fix),
hydration-failure-does-not-hang, and overlapping-removeSave-mutation-token.

Verified: `tsc --noEmit` clean, 82 frontend tests passing (78 + 4 new).
Backend untouched this round — 445 backend tests still the last-known-good
baseline.

### Follow-up — root-caused "the app is completely blank, no places/photos/menus anywhere"

Asked directly why nothing renders. Rather than guess, stood up the real
stack end to end: booted the backend locally against the existing seeded
SQLite DB, ran `npx expo start --web`, and drove it with headless
Playwright to see exactly what a user sees. First screenshot: a **fully
blank white page** — nothing at all, not even the tab bar. That matches
"blank, no food places photos or menus" exactly, because it's not any one
screen failing — the whole app never finishes loading.

Two confirmed, fixed bugs, both root causes (found in sequence — fixing
the first uncovered the second):

1. **`react-native-maps` has no real web support, and one bad import took
   down the entire bundle, not just the Map tab.** `app/(tabs)/map.tsx`
   does `import MapView, { Marker } from 'react-native-maps'`. That
   package's `lib/index.js` barrel unconditionally also pulls in
   `MapMarker.js`, which imports React Native's native-only
   `codegenNativeCommands` — Metro can't resolve that for the web platform
   and fails the bundle at build time, not runtime. Because expo-router's
   file-based routing uses `require.context` to eagerly scan and bundle
   *every* file under `app/` (so it can build its route table) regardless
   of which tab is active, that one unresolvable import failed the whole
   web bundle — every screen, not just Map. Adding a platform-specific
   `app/(tabs)/map.web.tsx` override alone does **not** fix this —
   confirmed empirically: `require.context` still statically requires both
   `map.tsx` and `map.web.tsx` (both match its route-file glob), so
   `map.tsx`'s bad import still poisons the bundle even though it's never
   the screen actually rendered on web. Fixed with both pieces together:
   `app/(tabs)/map.web.tsx` (a plain "not available on web" screen, no
   `react-native-maps` import at all) plus a new `metro.config.js` that
   redirects the whole `react-native-maps` package to Metro's built-in
   `{ type: 'empty' }` resolution specifically for `platform === 'web'` —
   the actual fix that stops Metro from ever trying to resolve the bad
   import in the first place.
2. **Fixing #1 uncovered a second, unrelated bundle-breaking bug:**
   `zustand`'s package.json `exports` map offers an ESM build
   (`esm/middleware.mjs`, `esm/index.mjs`) that calls `import.meta.env`
   (a Vite-specific check) — and Metro resolved `import ... from
   'zustand/middleware'` (used by `cravesStore.ts`) to that ESM build over
   the CJS one, even though Metro's own bundle output can't execute
   `import.meta` at all. This crashed every screen at runtime with
   "Cannot use 'import.meta' outside a module" — confirmed by grepping the
   actual served bundle for `esm/middleware.mjs`/`esm/index.mjs` before and
   after each attempted fix. Setting `resolver.unstable_conditionNames`
   directly did **not** change which build got picked (confirmed
   empirically — same `.mjs` files still in the bundle after). What
   actually fixed it: `resolver.unstable_enablePackageExports = false` in
   the same new `metro.config.js`, which makes Metro ignore the `exports`
   map entirely and fall back to `resolverMainFields`
   (`['react-native', 'browser', 'main']`) — for zustand's plain
   `"main": "./index.js"`, that always lands on the CJS build regardless
   of platform.

Verified both fixes are real and don't regress native: requested an actual
`platform=ios` bundle from the same Metro instance after the fix — 1422
modules, zero errors, zero stray `esm/*.mjs` matches (iOS was never
affected by either bug in the first place; this only confirms disabling
package-exports resolution globally doesn't break iOS's own resolution).
After both fixes, the exact same Playwright drive that produced a blank
page now shows the real Feed screen — CRAVE wordmark, city strip, "Test
Bistro" / "Second Spot" place cards with tier badges, bottom tab bar.

**This is a web-preview-specific bug pair** (`expo start --web` /
browser-based testing) — a native iOS/Android build was never affected by
either one, since native already resolves `react-native-maps` and
zustand's CJS build correctly on its own. If you're seeing the blank
screen on an actual phone (Expo Go or a built app) rather than in a
browser, this isn't the cause — see the `EXPO_PUBLIC_API_URL`/
`EXPO_PUBLIC_SUPABASE_URL` misconfiguration risks and the still-unset
prod secrets flagged earlier in this document instead. One more thing
`src/lib/supabase.ts` surfaced during this same investigation, worth
flagging regardless of platform: `createClient(supabaseUrl, ...)` runs
**unconditionally at module-import time** with no guard — if
`EXPO_PUBLIC_SUPABASE_URL`/`EXPO_PUBLIC_SUPABASE_ANON_KEY` are empty or
malformed in whatever build is running (same class of misconfiguration
risk `.env.example` already documents for `EXPO_PUBLIC_API_URL`, but
strictly worse here), Supabase's own client throws synchronously
("supabaseUrl is required"), which crashes the entire React tree before
any screen — including the tab bar — ever renders. That failure mode is
platform-agnostic (it would crash a native build exactly the same way) and
was reproduced directly during this investigation. Not fixed here (no
safe default URL to fall back to), just flagged as a real, previously
undocumented crash-at-launch risk if those two env vars are ever wrong in
a shipped build.

Verified: `npx tsc --noEmit` clean, 82 frontend tests passing, 445 backend
tests passing.

### Follow-up — root-caused "no photos" against the real production backend, and fixed it

Traced this all the way through against the actual deployed Railway
backend (`crave-production.up.railway.app`), not a local test DB — health
check confirmed `db: ok, cache: ok, worker: ok`, and `GET /api/v1/places`
returned real production data: **29,271 places**, including well-known
real restaurants (Omakase, Osteria Mozza, Sons & Daughters, Lord Stanley,
Hayato) with real `primary_image_url` values already populated. So the
ingestion pipeline had done its job — this wasn't "no photos were ever
fetched."

Then actually fetched one of those exact, currently-listed, currently-
served `primary_image_url` values (`GET /api/v1/image?ref=...` for
Omakase). Result: `{"detail":"Image not found"}` — a real photo reference,
for a real active place, that our own image proxy (`app/api/v1/routes/
image.py`) can no longer resolve against Google's Places API (New) media
endpoint.

Root cause: Google's Places API (New) photo resource names are not
permanent — they can and do go invalid over time. `app/workers/
image_worker.py::_needs_image_work_clause` only ever selects places with
too few images or no primary image at all; once a place clears that bar
even once, nothing ever revisits it again. `STALE_IMAGE_DAYS = 30` existed
as a named constant with a docstring literally explaining this exact gap
("Stale refresh... is NOT selected here — it requires explicit
force_refresh=True") — but nothing in `app/scheduler.py`'s automatic
`image_ingestion` job (every 20 minutes, `force_refresh=False`) ever passed
that flag, so `STALE_IMAGE_DAYS` was dead: defined, documented, and never
acted on. With a 29k-place catalog ingested over time, this guarantees
every photo eventually breaks permanently with zero automatic recovery.

Fixed by adding a third, bounded reserve to `_select_places` (alongside the
existing rank_score-priority slice and the starvation-fairness reserve from
earlier this session): up to `max(1, limit // 10)` places per run, selected
by oldest-primary-image-first, for places whose current primary image was
set more than `STALE_IMAGE_DAYS` ago — regardless of whether they already
have "enough" images by `_needs_image_work_clause`'s count. Places selected
this way get `force_refresh=True` passed to `ImageIngestService.
ingest_place_images` specifically (bypassing its own "already has images"
skip) while everything else in the same batch keeps using the caller's
original `force_refresh` value, so a stale-refresh cycle failing
repeatedly still trips the normal `image_blocked` safety net instead of
retrying forever. Also added a backfill step so an under-filled stale (or
starvation) reserve doesn't just shrink the batch below `limit` — the
unused capacity falls back to the next-best priority-ordered places,
using the same over-fetch-then-filter-by-picked-ids pattern already
established for the starvation reserve.

New tests: `test_select_places_reserves_slots_for_stale_primary_images`
(a place with a full, otherwise-acceptable gallery but a primary image
older than STALE_IMAGE_DAYS gets picked up and reported in the new
`stale_refresh_ids` return value) and
`test_select_places_does_not_treat_a_fresh_primary_image_as_stale`
(regression guard — a recent primary image must not get swept in just
because the place also needs other work). `_select_places` now returns
`Tuple[List[Place], Set[str]]` instead of a plain list — updated the two
existing starvation-reserve tests to unpack accordingly.

Separately confirmed (but not fixed, since it needs a Railway secrets/env
change, not a code change): the deployed backend is currently reachable
and healthy — this specific "reportedly crashed for ~2 months" note
earlier in this document is stale as of this check.

Verified: 447 backend tests passing (445 + 2 new), same command as every
other round this session.

### Follow-up — made refreshed photos durable (R2), and fixed a gallery-bloat bug the stale-refresh fix itself introduced

Asked why photos aren't already durably cached given the response already
sets `Cache-Control: max-age=31536000, immutable`. Real distinction: that
header caches the response on the *client's* side once they've
successfully loaded it — it says nothing about whether *we* own a durable
copy. Checked directly: user-uploaded photos are downloaded and stored in
R2 (`orig_key`/`processed_key`/`thumb_key`, real durable storage); every
Google-sourced photo — all 29k places' worth — has `PlaceImage.url` set
directly to Google's own (not-permanent) photo reference, confirmed by a
comment in `place_image.py` itself ("place_id images ingested from Google
Places never set these — they use `url` directly instead"). The periodic
re-validation fix from the entry above only patches the symptom; it still
depends on Google's link every single time, forever.

While designing the durable fix, found something that changes it: Google's
Places API (New) photo resource names are **session-scoped, not stable
identifiers for the same physical photo** — a fresh `GoogleImageFetcher.fetch()`
call for a place that already has photos returns different reference
strings than last time, even for what's logically the same picture.
`MaterializeImageTruth.write()`'s dedup keys strictly on that exact string
match (`existing_by_url`). This means the stale-refresh reserve from the
entry above — which calls `ingest_place_images(force_refresh=True)` — has
a **real, confirmed gallery-bloat bug of its own**: every ~30-day refresh
cycle for a given place adds a fresh set of gallery rows without ever
removing the old ones, since the new Google references never match what's
already stored. Nothing prunes old `place_images` rows anywhere in the
ingestion pipeline. Over enough cycles across 29k places, this compounds
indefinitely. This was never triggered before this session because nothing
called `force_refresh=True` automatically until the stale-refresh reserve
did.

Deliberately scoped the fix narrow (explicit choice, not the full "every
photo route through R2 with content-hash dedup" version, which would touch
the shared gallery-building pipeline all 29k places' initial ingestion
already relies on, need a schema change, and can't be smoke-tested against
a real R2 bucket from this environment — no live credentials available
here):

- `app/services/upload/r2_client.py` — added `upload_bytes()`, a
  server-side `put_object` call (the existing functions only generated
  presigned URLs for client-driven uploads).
- `app/services/images/google_photo_downloader.py` (new) — downloads the
  actual bytes for a Google photo resource name, reusing the same
  ref-validation regex `app/api/v1/routes/image.py`'s proxy already
  enforces (checked independently here too, since this has its own,
  separate caller).
- `app/services/images/stale_image_refresher.py` (new) —
  `StaleImageRefresher.refresh_primary()` fetches one fresh candidate from
  Google, downloads it, uploads to R2, and updates the place's *existing*
  primary `PlaceImage` row in place (new `url` + `created_at` reset) —
  deliberately not the gallery-rebuild pipeline, so there's no dedup
  question at all: it already knows exactly which row it's replacing, and
  creates zero new rows.
- `app/workers/image_worker.py` — `run()` now routes stale-refresh-reserve
  places through `StaleImageRefresher.refresh_primary()` instead of
  `ingest_service.ingest_place_images(force_refresh=True)`, closing the
  bloat bug and making the photo durable in the same step. Non-stale places
  are unaffected — still the original `ingest_place_images` path with the
  caller's own `force_refresh`.

New tests: `test_google_photo_downloader.py` (5, ref validation/success/
failure), `test_stale_image_refresher.py` (5, success path updates the
existing row with zero new `PlaceImage` rows created; every failure mode —
no primary, no candidates, download fails, upload raises — leaves the
existing primary untouched and returns `False`), `test_image_worker_run_stale_refresh.py`
(2, confirms `run()` actually routes a stale-selected place through the
refresher and never through `ingest_service` for that same place, and that
a refresh failure still feeds the existing `image_fetch_attempts`/
`image_blocked` safety net).

Verified: 459 backend tests passing (447 + 12 new).

Still open: this only replaces a photo once it's already gone through a
stale-refresh cycle — a brand-new place's first-ever photo is still a raw
Google reference until its first ~30-day refresh. Making *every* photo
durable from the moment of first ingestion is the fuller fix, deliberately
not done here (see scope note above) — would need the gallery pipeline's
dedup switched from reference-string matching to content-hash matching
(the `phash`/`is_duplicate_image` code the user-upload pipeline already
has) plus a schema change, and should get an actual live-R2 smoke test
before being trusted at 29k-place scale.

### Follow-up — built restaurant/user menu self-submission end-to-end (DoorDash/UberEats scraping explicitly deferred, not authorized)

Compared CRAVE's menu/photo pipeline against how competitor apps (Beli, and
generic DoorDash/UberEats/Yelp-clone architecture research the user pasted)
get their initial menu coverage. The honest answer for "how did small apps
get menus active initially": (1) scraping the restaurant's own site/POS
provider (Toast/Clover/Square/etc. — CRAVE already has all of these), and
(2) letting the restaurant or a user just tell you. CRAVE had (1) but never
built (2) — there was no path for a menu to enter the system except a
scraper finding one. DoorDash/UberEats aggregator scraping was researched
and scoped but **deliberately not built** — that's scraping a competitor
platform's own listings, a real ToS/legal question the user explicitly
said to hold off on ("hold off on uber and door dash").

Self-submission was built as a moderated *input* into the existing
multi-source truth pipeline, not a second, parallel "menu" system:
submission → moderator review → on approval only, written as ordinary
`PlaceClaim` rows → the same `materialize_menu_truth` → `MenuPublisher`
pipeline every scraper output already goes through. A submission is
therefore scored, corroborated, or outranked by whatever else exists for
that place using the same trust math (`score_candidates.py`) as any other
source — never a silent overwrite.

**Backend:**
- `app/db/models/menu_submission.py` (new) — `MenuSubmission`: place_id,
  submitted_by (server-derived, never client input), items (JSON,
  validated at the API boundary), status (pending/approved/rejected),
  reviewed_by/reviewed_at/rejection_reason. Registered in
  `app/db/models/__init__.py`.
- `alembic/versions/x1y2z3a4b5c6_add_menu_submissions_table.py` (new) —
  creates `menu_submissions` with both indexes, existence-guarded like the
  repo's other new-table migrations for the dual-lineage baseline reason
  documented in `k1l2m3n4o5p6`.
- `app/services/menu/user_submission_service.py` (new) —
  `apply_approved_submission()`: for each submitted item, builds the same
  fingerprint (`build_menu_fingerprint`, price excluded from identity like
  every other source) and upserts a `PlaceClaim` keyed on
  `(place_id, field="menu_item", claim_key=fingerprint, source="user_submission")`
  — a second submission for the same item updates the existing claim
  in place rather than creating a competing duplicate under the same
  source. Sets `is_verified_source=True` and `is_user_submitted=True`
  together (moderator approval means the trust-weight penalty in
  `score_candidates.py` for unverified user submissions — 0.9x — correctly
  doesn't apply), confidence intentionally below a typical scraper's
  starting point (0.75) so one self-reported submission doesn't
  automatically outrank a corroborated multi-source scrape. Then calls
  `materialize_menu_truth()` + `MenuPublisher().publish()`, same as every
  other pipeline entry point.
- `app/api/v1/routes/menu_submissions.py` (new) — `POST
  /places/{place_id}/menu/submit` (auth required, 404 if place doesn't
  exist, max 200 items/submission); `GET /moderation/menu-submissions`
  (queue) and `POST /moderation/menu-submissions/{id}/review`
  (approve/reject), reusing `moderation.py`'s existing `require_admin`
  dependency (`ADMIN_USER_IDS` allowlist, 404 not 403 for non-admins) —
  same gate as the photo-report queue, not a second admin system.
  Re-reviewing an already-decided submission 409s. Registered both routers
  in `app/api/v1/routes/__init__.py`.
- **Found, not fixed (logged for later)**: `app/services/menu/claims/menu_claim_builder.py`'s
  `build_menu_items()` constructs `MenuItem(section=..., price=...,
  currency=...)` — kwargs that don't exist on the real
  `MenuItem.__init__` (which takes `category`/`price_cents`, no
  `currency`). Every call raises `TypeError`, silently swallowed by a
  broad `except Exception`, so the function always returns `[]`. Confirmed
  via grep this is dead code — `build_menu_items`/`upsert_menu_items`/
  `replace_menu_items` are never called anywhere in the live pipeline —
  so it's inert, not a live bug, but worth fixing or removing later.

New tests: `tests/test_menu_submissions.py` (12) — submission creates a
pending row with server-set `submitted_by`; unknown place 404s; empty
items 422s; queue/detail/review all 404 for non-admins; reject records
reason and writes zero claims; re-reviewing an already-decided submission
409s; approving writes verified+user-submitted claims and actually
publishes real `MenuItem` rows; a second approval for the same item
updates the existing claim instead of duplicating it.

Verified: 471 backend tests passing (459 + 12 new). Frontend: `npx tsc
--noEmit` clean, `npx jest` 82/82 passing (no new frontend tests needed —
`MenuSubmissionSheet.tsx` is a straightforward form component with no
branching logic worth a dedicated test beyond what typecheck+manual review
already covers).

**Frontend:**
- `src/api/menu.ts` — added `submitMenu()`, converts whole-dollar price
  input to `price_cents` at the boundary so every caller doesn't have to
  remember the backend's unit.
- `src/components/MenuSubmissionSheet.tsx` (new) — modal form, add/remove
  multiple items (name required, category/price/description optional),
  client-side price validation, same bottom-sheet pattern as
  `ReportPhotoSheet.tsx`/`ShareLinkSheet.tsx`.
- `app/place/[id].tsx` — wired in: a "Add menu items" / "Suggest a
  correction" button under the Menu section (label changes based on
  whether a menu already exists), gated behind sign-in like the existing
  add-photo action. Submitting shows a toast — deliberately doesn't
  optimistically update `menuItems`, since nothing is live until a
  moderator approves it.

Still open / not done this pass (all explicitly deferred by the user, not
overlooked): DoorDash/UberEats scraping; a dedicated in-app moderator UI
for the new queue (currently API-only, same as the existing photo-report
queue); rate-limiting repeat submissions from the same user for the same
place beyond the general `rate_limit` dependency already on the routes.

### Follow-up — root-caused why photos were STILL broken after the stale-refresh fix: R2 public URLs were never actually public

Live-diagnosed against the real production Railway service and Cloudflare
dashboard (user pasted deploy logs, R2 bucket Objects tab, and R2 bucket
Settings). Two real findings, in order of how they were found:

1. **The R2 bucket had 0 objects and 0 operations, ever** — not just for
   the new stale-refresh fix, but for the entire lifetime of the app,
   including the pre-existing user-photo-upload feature
   (`image_processing_worker.py`) and profile-picture upload
   (`profile.py`), both of which already called the same
   `generate_public_url()`. Nothing durable has ever actually landed in
   R2.
2. **The actual cause, confirmed at the code level**:
   `app/services/upload/r2_client.py`'s `generate_public_url()` built
   every "public" URL from the **R2 S3 API endpoint**
   (`{bucket}.{account_id}.r2.cloudflarestorage.com`) — the host `boto3`
   authenticates against with the access key/secret. That host always
   requires SigV4-signed requests; it is not, and was never going to be,
   loadable by a bare `<img src>` in the app, regardless of any bucket
   "Public Access" toggle. Confirmed the bucket's actual Settings tab: no
   custom domain, and "Public Development URL" was disabled — there was
   no publicly-reachable domain configured at all, and even enabling one
   wouldn't have helped until the code stopped pointing at the API host.

Fix: R2 has a real public-serving domain once "Public Development URL" is
enabled on the bucket (`https://pub-<hash>.r2.dev`, or a mapped custom
domain for production). User enabled it and provided the resulting URL.

- `app/services/upload/r2_client.py` — added `R2_PUBLIC_BASE_URL` (new
  required env var). `generate_public_url()` now builds off that instead
  of the S3 API host, and **raises** `RuntimeError` if it's unset rather
  than falling back to the old (always-broken) behavior — silently
  writing another unreachable URL is worse than failing loudly.
- `app/services/images/stale_image_refresher.py` — moved the
  `public_url_fn(key)` call inside the same try/except as `upload_fn`, so
  a misconfigured `R2_PUBLIC_BASE_URL` fails `refresh_primary()` closed
  (existing primary row untouched, returns `False`) instead of raising
  uncaught out of the per-place loop. `image_worker.py`'s own outer
  try/except would have caught it too, but failing closed at the source
  matches every other failure mode `StaleImageRefresher` already handles
  the same way.
- `tests/conftest.py` — set a default `R2_PUBLIC_BASE_URL` for the test
  environment (real value doesn't matter, just needs to exist) — several
  existing tests exercise the real upload pipeline against a mocked S3
  client but still call the real `generate_public_url()`.

New tests: `tests/test_r2_client.py` (4 — raises when unconfigured,
builds the correct URL from the base, strips a trailing slash, and a
regression guard that the S3 API host never appears in the output),
`tests/test_stale_image_refresher.py` (+1 — a raising `public_url_fn`
leaves the existing primary untouched and returns `False`, mirroring the
existing upload-raises test).

Verified: 476 backend tests passing (471 + 5 new).

**Required action, not yet done (needs the user's Railway dashboard,
same as SUPABASE_JWT_SECRET elsewhere in this doc)**: add
`R2_PUBLIC_BASE_URL` to Railway's service variables, set to the bucket's
Public Development URL. Without it, every upload path that calls
`generate_public_url()` (stale-photo refresh, new user photo uploads,
profile picture uploads) will fail closed — better than silently writing
another unreachable URL, but still means photos stay broken until this
env var exists in production.

Still open: this fixes URLs for photos uploaded *after* the fix deploys
and the env var is set. It does not retroactively fix any `PlaceImage`
row whose `.url` already points at a dead Google session reference or
(for user-uploaded photos, if any ever silently succeeded before this
fix some other way) the old unreachable R2 API host — those still need
the existing stale-refresh reserve to cycle through them, or a one-off
backfill script, neither of which was run here.

### Follow-up — root-caused the actual reason a specific production photo stayed broken: the R2 key restriction, and a real duplicate-primary invariant bug found live

Continued diagnosing the same "Omakase" place from the R2 fix above,
live against production via Railway's Console tab (the user ran scripts I
wrote, pasted output back). Two more real, confirmed findings:

1. **The only Google Cloud API key in the project was restricted to
   "Android apps"** — an application restriction meant for the mobile
   app's own Maps SDK, requiring headers (package name + signing cert)
   that only a real Android device sends. The backend was reusing this
   exact key (`GOOGLE_PLACES_API_KEY`) for four different server-side
   call sites — legacy Places Nearby Search (discovery), Places API (New)
   Text Search, Places API (New) photo media, and Cloud Vision (safety
   scanning + menu OCR) — all four rejected with 403 PERMISSION_DENIED,
   unconditionally, for every request, regardless of staleness. This was
   never going to work from the day this key got wired server-side. Fix
   was a Google Cloud Console action, not code: user created a second key
   with Application restrictions = None, API restrictions = Places API +
   Places API (New) + Cloud Vision API, and replaced
   `GOOGLE_PLACES_API_KEY` in Railway with it. Confirmed by watching the
   upstream status code on the same photo proxy request change from 403
   to 400 after the swap (400 = genuinely invalid/expired reference,
   which is a normal, expected outcome for an old Google photo ref, not a
   config problem).

2. **`PlaceImageInvariantService` was found, live, with two
   `is_primary=True` rows for the same place** — an old Google Places
   photo (confidence 0.8, dead reference) and a newer, working, durably-
   hosted photo scraped from the restaurant's own website (confidence
   0.556, `images.squarespace-cdn.com`). This should be structurally
   impossible (`repair()` is supposed to run after every ingestion write
   and demote all but one primary) — diagnosed by running `repair()`
   directly via the production console, which **actively made the bug
   worse**: `_fix_duplicate_primary`'s winner-selection picked purely by
   confidence score, so it decisively demoted the *working* photo and
   kept the *dead* one as primary. Manually reverted that via console
   immediately after finding it (raw UPDATE flipping `is_primary` back).

   Root cause: `confidence`/`quality_score` measure extraction quality at
   ingestion time, not whether a URL still resolves — and Google Places
   (New) photo references are session-scoped, so an old high-confidence
   Google reference will systematically outscore a newer, lower-
   confidence, but actually-working durable photo, every time this
   conflict occurs. With ~29k places and photos ingested from multiple
   sources over time (Google backfill + later website scraping), this
   pattern is very unlikely to be unique to the one place found here.

   - `app/services/images/place_image_invariant_service.py` — added
     `_is_ephemeral_google_ref(url)` (true for both the bare
     `places/{id}/photos/{id}` resource-name form and the full
     `places.googleapis.com` URL form — same two shapes
     `place_image_visibility_query.py` already checks for). Both
     `_fix_duplicate_primary` and `_promote_best_eligible`'s winner-
     selection now sort by `(not _is_ephemeral_google_ref(url),
     quality_score_or_confidence)` — a durable URL always beats a raw
     Google reference regardless of confidence gap; confidence only
     breaks ties within the same durability class (two durable URLs, or
     two Google refs, unchanged from before).

   New tests: `tests/test_place_image_invariant_service.py` (9, no prior
   test file existed for this service at all) — covers
   `_is_ephemeral_google_ref`'s four cases, the exact production
   scenario (durable beats higher-confidence Google ref), confidence
   still deciding within the same durability class, hidden primaries
   still excluded, a no-op when there's no duplicate, and the same
   durability preference applying to `_promote_best_eligible`.

Verified: 485 backend tests passing (476 + 9 new).

**Update — the production sweep was run.** Rather than looping all
29,626 places (the first attempt at this — ~1 place/sec of DB round-trip
latency, projected multiple hours), switched to two bulk SQL queries to
find the actually-affected places directly (`GROUP BY place_id HAVING
COUNT(*) > 1` for duplicate primaries, plus a hidden-primary query), then
ran `repair()` only on that set. Real result: **27 affected places** out
of 29,626 (not the widespread issue it could have been) — all repaired,
cache invalidated. Confirms this bug class was real but narrow in scope.

### Follow-up — measured the real menu-coverage gap, and built an LLM extraction fallback (DeepSeek) for the part of it that's fixable

The "why don't most places have a menu" question turned out to need a
real number, not the 10-place anecdotal sample this session had been
running on all night. Queried production directly:

- **738 of 29,626 places have a menu (2.5%).**
- Of the 28,888 without one: **10,016 (34.7%) have a website/Grubhub/menu
  source on file** — genuine extraction-fallback candidates, where a real
  page exists and every current strategy still finds nothing in it.
- **18,872 (65.3%) have no source at all** — no website, no Grubhub link,
  no discovered menu URL. This is a **discovery/enrichment gap, not an
  extraction gap** — no smarter parsing touches it; explicitly out of
  scope for this pass, logged here as the actual larger lever for a
  future session (most likely fix: backfilling `Place.website` via a
  Google Place Details call for places that don't have one).

For the 10,016 addressable places: live-traced one real failure
(`fishgutscalifornia.com`) through the full pipeline. The page fetched
fine — 200 OK, ~80KB of real HTML, no blocking — and all 7 pattern-based
extraction strategies (JSON-LD, hydration state, JS-bundle parsing, API
endpoint discovery, raw HTML selectors, iframe detection, provider
integrations) found 0 items in content that was genuinely present. This
confirmed the actual bottleneck: arbitrary restaurant sites' markup
defeats hardcoded selectors, and browser escalation (headless rendering)
doesn't help this failure mode specifically, since the content was
already in the plain-fetched HTML — re-rendering doesn't change a
structure that heuristics already failed to recognize.

Researched what other apps/teams actually do for this class of problem
(cited sources in-session): LLM-based extraction is the current standard
fallback precisely because it reads page semantics instead of matching
fixed selectors, so it doesn't break on a site with unusual markup the
way pattern-based code does — used as a fallback *after* structured-data
extraction, never a replacement for it (CRAVE's existing 7-strategy order
already gets this right).

- `app/services/menu/extraction/llm_menu_extractor.py` (new) —
  `extract_llm_menu(html, url)`: strips HTML to visible text
  (BeautifulSoup, already a dependency — drops script/style/nav/footer/
  header/svg to keep token count down), sends it to DeepSeek's
  OpenAI-compatible chat completions endpoint with a strict
  name/section/price_cents/description JSON schema in the system prompt,
  parses the response into the same `ExtractedMenuItem` contract every
  other strategy already produces. Never raises — missing API key,
  network failure, non-200, malformed JSON all fail closed to `[]`, same
  contract as every other extractor in the router.
- `app/services/menu/menu_extraction_router.py` — added
  `_safe_llm_extract()` and wired it into `_run_extraction_pass` as the
  true last resort: tried only after all 7 free strategies produce
  nothing (`fallback` still empty), and tried *before* browser escalation
  rather than after, since escalation doesn't help this specific failure
  mode. Re-tried once more if escalation does find genuinely different
  HTML (`allow_llm_fallback` threaded through the recursive call). Never
  called when a cheaper strategy already found enough items — cost only
  incurred on genuine last-resort cases.
- Chose DeepSeek over Anthropic for this specific call site on cost
  grounds, researched and priced in-session: this is bounded, high-volume,
  low-complexity structured extraction (not open-ended reasoning), and at
  DeepSeek's pricing the entire 10,016-place addressable backfill costs
  roughly **$10** (stripped text, ~5K tokens/call) versus roughly $385 at
  Haiku 4.5 pricing for the same job. Also compared against Qwen3.7 Flash
  and Ling-2.6-flash, which are technically cheaper per token still —
  stuck with DeepSeek anyway since the absolute dollar gap at this volume
  is small (~$20) and DeepSeek has the more proven, better-documented
  production API of the three.

New tests: `tests/test_llm_menu_extractor.py` (13 — HTML-to-text
stripping, JSON parsing including a markdown-fence-wrapped response,
missing/malformed rows, the full extract_llm_menu path with the HTTP call
mocked: happy path, missing key, empty html, non-200, network error,
malformed response shape), `tests/test_menu_extraction_router_llm_fallback.py`
(4 — LLM fallback fires and its result is used when every heuristic finds
nothing; does *not* fire when a cheap strategy already succeeded — the
main cost-control invariant; empty LLM result still returns the pipeline's
normal empty fallback rather than erroring; an LLM-extractor exception
doesn't crash extraction). One test-hygiene bug caught and fixed while
writing these: an early version of the "already succeeded" test left
`discover_api_endpoints` unmocked, which made real speculative network
calls to nonexistent test-domain endpoints and added ~28s of real
timeout-driven latency to the suite — fixed by mocking it like every
other strategy in that test.

Verified: 504 backend tests passing (485 + 19 new).

**Required action, not yet done**: add `DEEPSEEK_API_KEY` to Railway's
service variables. Without it, `extract_llm_menu` fails closed (returns
`[]`, logged, no crash) — same as every other missing-credential case
this session.

Still open: this closes the *extraction* gap for the 10,016 places that
have a source but nothing readable in it — it does not touch the larger
18,872-place *discovery* gap (no source at all) described above, and it
hasn't been live-verified against a real production page yet (needs the
Railway env var added first, then a real run against
`fishgutscalifornia.com` specifically to confirm it actually closes that
exact case).

### Follow-up — found and fixed the actual reason the OSM discovery pipeline wasn't closing the 18,872-place gap, plus a production deploy failure

Traced the open thread from the previous entry: CRAVE already has a real,
correctly-built OSM/Overpass discovery pipeline (`osm_overpass.py` →
`osm_ingest_job.py`, nightly, rotating 5 cities/day, free/no API key) and
`promote_service_v2.py` already backfills `Place.website` onto an existing
matched place when discovered by any source — the exact mechanism the
pasted free-discovery research was suggesting be built from scratch. So the
question was why it wasn't already closing the gap.

Found it: `osm_overpass.py` set every OSM candidate's `confidence` to
**0.6**. `promotion_orchestrator_v2.MIN_CONFIDENCE_THRESHOLD` is **0.72** —
candidates below it are never promoted. Automated sources like OSM never
pass a `contributor_key`, so `candidate_store_v2`'s merge logic takes
`max(old, new)` on re-scans rather than accumulating (correct for user-
corroboration sources like GPS/share/hitlist signals, where the same
contributor re-submitting shouldn't inflate confidence — but it means an
automated source's confidence can never grow past its ingest-time value).
**Every OSM-discovered candidate was therefore permanently stuck at 0.6,
below the gate, forever** — ingested nightly, never promoted, never
backfilling a single website, regardless of how good the underlying data
was. Government health-inspection data (0.75–0.9) and geocoded records
(0.75) both already clear the bar; OSM was the one source that didn't,
apparently never recalibrated against the threshold when it was added.

Fix: `osm_overpass.py`'s `confidence` raised from 0.6 to 0.75, matching the
value already used for comparably-sourced automated/geocoded data elsewhere
in this package. This doesn't bypass any dedup or entity-matching logic —
it only changes whether a candidate clears the existing promotion gate;
`promote_candidate_v2`'s real entity-match/backfill-or-create logic runs
exactly as before. `_job_discovery` (every 5 minutes, source-agnostic) will
pick these up automatically once deployed — no separate wiring needed.
New test: `tests/test_osm_overpass.py` (7 tests — field mapping, missing
name/coordinates, non-200/exception handling, way/relation center
coordinates, and the regression itself: asserts the returned confidence
clears `MIN_CONFIDENCE_THRESHOLD`).

**Still needs a live-production step the user should run**: existing
already-ingested OSM candidate rows are stuck at the old 0.6 value in the
DB — the code fix only affects newly-upserted/re-scanned rows, and since
0.75 > 0.6, the *next* nightly re-scan of each city will naturally bump
them (self-heals over the ~(active_cities / 5)-day rotation). To close the
gap immediately instead of waiting on the rotation, a one-time
`UPDATE discovery_candidates SET confidence_score = 0.75 WHERE source = 'osm' AND confidence_score < 0.75;`
run once (e.g. via Railway Console) unblocks every already-ingested OSM
candidate on the very next discovery cycle (every 5 min) instead of waiting
on the rotation.

Also root-caused a failed Railway deployment shown to have healthchecks
time out ("1/1 replicas never became healthy!") despite the build and
container start both succeeding — `railway.json`'s `healthcheckTimeout`
was 30s, but the start command is `alembic upgrade head && uvicorn ...`,
meaning migrations, module imports, a DB roundtrip
(`_startup_validation`), and full APScheduler job registration (8 jobs)
all have to finish serially before the port even opens — 30s is tight for
that under any deploy-time variance, and this specific attempt seems to
have blown through it (later logs from the same window show the container
did fully start and pass `startup_validation`, just too late for the
healthcheck to see it). Bumped to 100s — a config change only, no behavior
change on a healthy deploy, just more patience before Railway gives up.

Verified: 511 backend tests passing (504 + 7 new), frontend `tsc --noEmit`
clean.
