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

### Follow-up — built a second, free discovery source (Overture Maps) for the 18,872-place gap, live-verified before writing any code

User asked for a cheaper way to backfill websites than Google Place
Details, initially suggesting DeepSeek directly. Corrected that: DeepSeek
has no live web access in how it's called here (one static text-in
request) — asking it "what's this restaurant's website" would make it
guess from training data, which for a discovery app risks confidently
linking the wrong business's site. Not a cost problem, a capability
mismatch.

The actual free option — already named in the user's own earlier pasted
research — is Overture Maps: monthly public GeoParquet on S3 (Meta/
Microsoft/Amazon/TomTom-backed), no API key, no per-request cost. Verified
this was real and worth building *before* writing any ingestion code, not
after: queried the real dataset live (anonymous S3 access via pyarrow,
since DuckDB's httpfs extension download was blocked by this environment's
egress policy — worked around it with `pyarrow.fs.S3FileSystem(anonymous=
True)` + `pyarrow.dataset` filter pushdown on the `bbox` struct's min/max
stats, which turned out to prune all-but-one of the 16 global part-files
for a single-city bounding box in under a second each).

Live result for a real SF-area bbox: **9,447 food/drink places, 85.2% with
a website, average confidence 0.89.** Flagged the honest caveat to the user
before proceeding: that's coverage for *every* food place Overture knows
about in the area, not specifically CRAVE's 18,872-place gap — those
places already failed to yield a website through both Google Places
Nearby Search and OSM, a harder, adversarially-selected subset, so the
real yield is very likely lower than 85%. User chose to build now and
measure the real yield from production once live rather than gate the
build on a pre-check, given the pipeline is free, additive, and reversible
(everything still flows through the existing entity-match/dedup gate).

Also caught and fixed a taxonomy issue before it became a bug: Overture's
category names aren't safe to substring-match (`"bar" in category` would
wrongly match `barber_shop`). Used `taxonomy.hierarchy` instead — confirmed
live that all real restaurant/cafe/bar categories carry `hierarchy[0] ==
"food_and_drink"` while unrelated categories don't, so filtering on that
grouping is exact, not heuristic.

- `app/services/discovery/overture_places.py` (new) —
  `fetch_overture_places(lat_min, lat_max, lon_min, lon_max)`: discovers
  the current dated release via an unsigned/anonymous boto3 S3 list call,
  reads the `theme=places/type=place` Parquet with pyarrow's bbox filter
  pushdown, keeps only `food_and_drink`-hierarchy rows, maps to the same
  output shape `osm_overpass.py` already produces. Confidence is a flat
  **0.8** — deliberately NOT Overture's own per-record confidence field,
  since individual real rows legitimately score anywhere from ~0.5-1.0 in
  Overture's own scale and reusing that directly would reintroduce the
  exact bug just fixed for OSM (see previous entry) one field over. Fails
  closed to `[]` on any error (missing release, S3/network failure).
- `app/services/discovery/overture_ingest_job.py` (new) —
  `run_overture_city_ingest(db, limit, today)`, a deliberate structural
  mirror of `osm_ingest_job.py` (same day-based city rotation, same
  `ingest_candidate_v2` upsert path), kept as its own copy rather than a
  shared import so the two sources' cadence/limits can diverge
  independently later.
- `app/scheduler.py` — added `_job_overture_ingest`, scheduled every 24h
  alongside the existing OSM job (9 scheduler jobs total now).
- `requirements.txt` — added `pyarrow>=15.0.0` (boto3 already present, was
  already a dependency for R2).

New tests: `tests/test_overture_places.py` (7 — field mapping, the same
confidence-clears-the-promotion-threshold regression test written for OSM,
`food_and_drink` taxonomy filtering excluding a same-substring false
positive like `barber_shop`, missing-release/exception handling,
missing-name skip, missing website/phone/address handled), 
`tests/test_overture_ingest_job.py` (11 — structural mirror of
`test_osm_ingest_job.py`'s suite: rotation, idempotency by external_id,
partial-batch failure handling, limit enforcement).

One test-hygiene bug caught by running the full suite twice, not just the
new files: the new ingest tests commit real `DiscoveryCandidate` rows
(confidence 0.8, above the promotion threshold) into the same on-disk
SQLite file every test module in this suite shares, and
`test_promotion_pipeline_v2.py::test_orchestrator_promotes_eligible_candidates`
counts *every* eligible candidate in the table with no scoping of its own
— previously safe by accident, since every other source's test fixtures
used confidence values below the threshold. Fixed by having the new
ingest tests' `db` fixture delete its own `source="overture"` rows in
teardown; didn't touch the pre-existing test's unscoped query, since
narrowing that was out of scope for this change.

Verified: 526 backend tests passing (511 + 15 new, confirmed stable across
repeated full-suite runs, not just in isolation).

**Still open**: this closes the *mechanism* gap (a second free acquisition
source, correctly calibrated to actually clear the promotion gate this
time) but the real yield against CRAVE's specific 18,872-place gap is
still unmeasured — needs the scheduled job to actually run against
production data, then a live count of how many gap places got a `website`
backfilled from `source="overture"` candidates.

### Follow-up — root-caused a live production crash silently dropping OSM candidates, found by reading real deploy logs 4 days after the previous fixes shipped

User pasted a routine production log check (image ingestion + OSM
acquisition + discovery cycle all running normally) that also contained a
repeating, unhandled `sqlalchemy.exc.MultipleResultsFound` traceback in
`osm_ingest_candidate_failed`. Root cause:
`candidate_store_v2.upsert_discovery_candidate_v2`'s name+city fallback
match used `.one_or_none()`, which raises the moment a city has more than
one `DiscoveryCandidate` row sharing a name. That's not an edge case —
only `(city_id, name, lat, lng)` together is unique
(`uq_candidate_city_name_location` on the model), not `(city_id, name)`
alone, and OSM legitimately produces this shape (the same real place
tagged twice — building outline and point — or two branches of one chain).
Every POI that hit an existing name collision was silently dropped from
that point on; `osm_ingest_city_ingest`'s per-POI try/except caught the
crash and logged it, so the job itself never died, but the data never
landed. Overture Maps runs through this exact same function, so it would
hit the identical failure the moment it found a same-named collision too.

Fix: replaced `.one_or_none()` with `.order_by(created_at.asc()).first()`
— picks the oldest existing row deterministically instead of crashing,
consistent with "update the existing record" being the whole point of a
fallback match in the first place.

New test: `tests/test_candidate_store_v2.py` (6 tests — first coverage
this file has ever had). The regression test needed to construct the
two-duplicate-rows precondition directly via the ORM rather than through
two calls to the function under test, because the function's own fallback
match already self-heals that shape on a normal path (a second upsert call
with a new external_id but the same name+city merges onto the first row
rather than creating a second) — matching how the real precondition
actually had to arise in production (two rows created through some other
means before ever colliding on a shared upsert call). Also caught and
fixed the same test-pollution class found earlier this session: this
file's `city` fixture now sweeps its own `DiscoveryCandidate` rows in
teardown so `test_promotion_pipeline_v2.py`'s unscoped global query
doesn't pick up leftover eligible candidates.

Verified: 532 backend tests passing (526 + 6 new). One transient failure
during verification (`sqlite3.OperationalError: disk I/O error` on an
unrelated test) turned out to be two overlapping local pytest invocations
against the same on-disk SQLite file, not a real bug — confirmed clean on
a serial rerun.

Also confirmed live in the same pasted log: OSM ingestion is genuinely
finding real, new places (`Millie's`, `El Faro Méxican Foods`, `Noah's
Bagels`, `Panama Bay Coffee Co.` in Pleasant Hill) and image invariant
repair is running clean (50/50 succeeded this cycle) — the pipeline built
earlier this session is alive and working end to end; this bug was only
costing some fraction of the candidates passing through it.

### Follow-up — root-caused why `overture_places` kept ModuleNotFoundError-ing on `pyarrow` across multiple otherwise-successful, otherwise-current deploys

Deploying this session's full set of fixes turned out to need many more
retries than expected, live-diagnosed turn by turn against real Railway
deploy logs and console sessions (Railway had a genuine US-West regional
outage in the middle of this that explained the first round of failures;
a stale local git checkout — 5 commits behind, from a branch history
rewrite earlier in the session — explained a second round; both closed
out). What was left after both of those: `DEEPSEEK_API_KEY` intermittently
reading `False` even on deploys confirmed to have the right code, and
`overture_places` raising `ModuleNotFoundError: No module named 'pyarrow'`
on every single deploy checked, including ones with `scheduler_started
jobs=9` (i.e. definitely running current code).

Root cause, found by reading the actual Build Logs rather than assuming
from the Deploy Logs alone: every one of these builds showed `pip install
-r requirements.txt cached 0ms` — Railway's build cache was reusing the
result of an *earlier* build where `pyarrow` silently failed to install
(pip completed with exit 0 and a "Successfully installed [long list]"
line that just never included pyarrow — never investigated why that first
failure happened, since it's now moot), and kept serving that same broken
cached layer on every subsequent deploy because `requirements.txt`'s bytes
hadn't changed since. No amount of redeploying — restart, dashboard
redeploy, repeated `railway up` — would ever fix this on its own, because
none of them changed the one thing the cache keys off.

Fix: bumped `pyarrow`'s floor from `>=15.0.0` to `>=18.0.0` in
`requirements.txt` — changes the file's bytes (forces a real reinstall)
while staying a floor, not an exact pin, consistent with every other
dependency in this file. `DEEPSEEK_API_KEY` reading `False` was very
likely a symptom of console sessions landing on a container from one of
these same stale-cache builds rather than a separate variable-injection
bug — no code or config change was needed for that once a genuinely fresh
build was confirmed.

Verified: 532 backend tests passing (unchanged — this is a pure dependency
version-floor change, no application code touched).

Still needs: one more deploy + the same verification script run once more
to confirm `pyarrow` actually installs this time (cache-busted, but not
yet re-verified against a live build as of this entry).

### Follow-up — built user-blocking and account deletion (two of the three App Store review blockers found earlier this session)

User asked what's actually left before this can go on the App Store and
be used end to end. Checked the real state of the code instead of
guessing: photo upload already exists (and now works, given this
session's R2/invariant fixes), but video upload doesn't exist at all
(only sharing an external video *link*, not uploading one), and three
App Store review requirements were unmet — no privacy policy, no
account-deletion flow (Guideline 5.1.1(v)), no user-blocking (Guideline
1.2, UGC apps — only photo *reporting* existed, not blocking a person).
Privacy policy is a hosting/content task, not something to build; the
other two are real engineering work, built this pass.

**User blocking** — `app/db/models/user_block.py` (new, mirrors
`user_follow.py`'s shape exactly: `(blocker_id, blocked_id)`, unique pair,
no-self-block check constraint), migration `y1z2a3b4c5d6`,
`app/services/social/block_service.py` (`block_user`, `unblock_user`,
`is_blocked` — deliberately symmetric, true if *either* side blocked the
other, since a blocked person losing visibility into the blocker is the
whole point — `list_blocked`, `blocked_user_ids_either_direction`),
`app/api/v1/routes/blocks.py` (`POST/DELETE /blocks/{id}`, `GET
/blocks/status/{id}`, `GET /blocks`). `block_user` also deletes any
existing `UserFollow` row in both directions, and `follow_service.
follow_user` now refuses a new follow between blocked users — checked
this actually closes the friends-feed gap for free: `get_friends_feed`
only ever reads from `list_following` (real `UserFollow` rows), so once a
block clears the follow relationship, blocked users' activity can never
resurface there without any separate filtering needed.

Frontend: `app/user/[id].tsx` gets a header "⋯" button (Block/Unblock),
and blocking now replaces their follow button + ranked list with a plain
"you've blocked this person" notice instead of still rendering their
content. `src/api/social.ts` gets `blockUser`/`unblockUser`/
`fetchBlockStatus`/`fetchBlockedUsers`.

Deliberately NOT done in this pass (real gap, not silently dropped):
blocked users aren't filtered out of search results or place-level
comment/crave lists yet — only the friends feed and follow relationship
are covered. Worth a follow-up sweep before shipping if App Review
specifically probes those surfaces.

**Account deletion** — `app/services/account/account_deletion_service.py`:
`delete_account(db, user_id)` deletes the `UserProfile` row and every
`UserFollow`/`UserBlock` row referencing this user, then calls Supabase's
Admin API (`DELETE {SUPABASE_URL}/auth/v1/admin/users/{id}`) to delete the
actual auth identity — this app never owned auth (Supabase does, see
`app/core/user_auth.py`'s docstring), so "delete account" has to mean
deleting that credential too, not just app-side data; otherwise someone
who "deleted their account" could still log back in with the same
email/password. Route: `DELETE /account/me`, requires `{"confirm": true}`
in the body as cheap insurance against an accidental/retried call actually
deleting something.

**Real, flagged gap, not yet resolved**: `SUPABASE_SERVICE_ROLE_KEY` and
`SUPABASE_URL` aren't configured anywhere in this codebase yet (confirmed
— the app has only ever verified incoming JWTs via `SUPABASE_JWT_SECRET`,
never made an outbound admin call to Supabase). Without them,
`delete_account` still deletes all app-side data but logs
`account_deletion_supabase_not_configured` and reports
`supabase_account_deleted: false` — fails visibly, not silently, but the
auth credential genuinely isn't deleted until those two env vars are set
(`SUPABASE_URL` = same value as the frontend's `EXPO_PUBLIC_SUPABASE_URL`;
`SUPABASE_SERVICE_ROLE_KEY` = Supabase dashboard → Project Settings → API
→ service_role secret — a real secret, never expose it client-side).

Deliberately scoped: does not sweep every other table referencing this
user_id (place claims, submitted photos, craves/rankings) — those are left
in place, same as most social apps handle deleted accounts (past public
contributions can remain, un-tied to a reachable profile). A full
data-retention audit is separate, real follow-up work, not silently
skipped.

Frontend: `app/settings.tsx` gets a "Delete Account" row with a two-step
destructive confirmation (the second step exists specifically because this
destroys the login itself, not just app data — one tap felt too easy for
something this irreversible), calling `deleteMyAccount()` then the
existing `signOut()`.

New tests: `tests/test_block_service.py` (12), `tests/test_account_
deletion_service.py` (7, Supabase's HTTP call always mocked — never a real
network call). Verified: 551 backend tests passing (532 + 12 + 7, stable
across repeated runs), frontend `tsc --noEmit` and `jest` both clean (82
frontend tests unaffected).

**Still open for real App Store readiness**: privacy policy (hosting/
content, not code — `settings.tsx` already links to `https://crave.app/
privacy` and `/terms`, but nothing confirms those pages exist), video
upload (doesn't exist at all — only external video link sharing), the two
Supabase env vars above, and the blocked-user filtering gap (search/
comments) noted earlier. Apple Developer enrollment, App Store Connect
listing, and TestFlight builds are process items outside what code can
resolve.

### Follow-up — deployed the Overture Maps commit and found pyarrow reliably fails to install during Railway's build, root cause still unresolved

Ran the actual deploy. Good news first: `scheduler_discovery_complete
promoted=2` appeared in production logs for the first time ever — real
evidence the OSM confidence fix is working, not just running. `user_blocks`
migration applied cleanly. `DEEPSEEK_API_KEY`/`SUPABASE_URL`/
`SUPABASE_SERVICE_ROLE_KEY` were all already configured (checked the
Variables tab directly — earlier assumption that Supabase's two vars were
missing was wrong).

`overture_places` still threw `ModuleNotFoundError: No module named
'pyarrow'` on every deploy checked, including builds confirmed to be
running current code (`scheduler_started jobs=9`). Tried, in order, none
of which fixed it: (1) bumping the version floor to bust a
content-hash-keyed build cache, (2) `NO_CACHE=1` (a documented Railway
fix for build-cache corruption — didn't help, consistent with a known gap
that `NO_CACHE` isn't always honored by the newer Railpack builder), (3)
`RAILPACK_INSTALL_CMD` overriding the pip step directly — this one
actively broke the build, because it replaced Railpack's *entire*
auto-generated install sequence (venv creation + pip install + Playwright
browser install), not just the pip line as hoped; the build then failed
outright trying to copy a Playwright cache directory that was never
created. Reverted immediately.

Confirmed via live diagnosis that pyarrow itself is completely fine:
running `pip install pyarrow` by hand in the Railway Console, on the
exact same container reporting the import error, succeeds instantly
(50MB wheel, full speed). So the package, the platform, and the network
are all fine — something specific to how Railway's *build* step invokes
pip is the actual problem, and four attempts at fixing it from the
outside (cache flags, version bumps, command overrides) didn't land.

**Decision: stop chasing this.** Overture Maps is a second, nice-to-have
discovery source — OSM alone is already confirmed finding real places in
production (`promoted=2` and multiple real restaurant names in the
logs). The accepted workaround going forward: run `pip install pyarrow`
manually in the Railway Console after any deploy that needs Overture
working (confirmed reliable every time tried, ~10 seconds). This does
not survive a container restart/redeploy and needs redoing each time —
a real, known limitation, not a silent gap.

### Follow-up — closed the two "without your input" gaps from the App Store punch list: leaderboard block-filtering and menu staleness re-verification

User asked what could be done with zero further input/decisions from
them. Two real, pure-code items from the earlier punch list qualified;
built both.

**Leaderboard block filtering** — re-checked the actual claim from
earlier ("blocked users still show in search/comments") against the real
code before building anything, since it turned out to be wrong on both
counts: `/search` is place search with no user identity involved at all,
and `/craves/for-place/{id}` deliberately never exposes `submitted_by`
(already privacy-safe by design, confirmed in that route's own
docstring). The one real gap was the **global** leaderboard
(`leaderboard_service.get_leaderboard`), which lists every ranked user's
name/avatar with no block-awareness — `among="friends"` was already
safe for free (it's scoped through `list_following`, and blocking already
clears follow relationships both ways), but `among="global"` had no
equivalent filter. Fixed: excludes `block_service.
blocked_user_ids_either_direction(db, user_id)` from the global query.
2 new tests in `tests/test_activity_and_leaderboard.py`.

**Menu staleness re-verification** — `menu_worker.py`'s
`_load_places_requiring_menu` excluded any place with an existing menu
`PlaceTruth` row *permanently*, with no way to notice a menu going stale
(price changes, a site redesign that breaks the extractor, a closed
restaurant). Added `MENU_STALENESS_DAYS = 60`: a place with a menu is now
re-eligible once its last real check
(`Place.menu_extraction_attempted_at`) is older than that window, or was
never stamped at all (every existing menu'd place predates this
mechanism — treated as eligible for one catch-up check rather than
needing a data migration). Also now stamps `menu_extraction_attempted_at`
on the *success* path in `run()`, not just failure — needed because
`materialize_menu_truth` skips updating `PlaceTruth.updated_at` when a
re-extraction hashes identical to what's already stored (its own,
separately-correct dedup optimization), so that column alone couldn't
serve as the staleness clock.

Found and fixed a real interaction bug while building this:
`_not_in_backoff_clause` had no branch for "0 failures, but the last
check is old" — a healthy place's `failure_count` resets to 0 on
success, and once staleness made it eligible again, none of the
existing count==1/2/3/4+ backoff branches ever match count 0, so it
would look permanently "in backoff" despite having never failed at all.
Added an explicit "0 or unset failure count is never backed off" branch
— backoff should only ever apply to places that have actually failed.

Updated the one existing test whose name/assertion described the old,
now-deliberately-changed permanent-exclusion behavior
(`test_a_place_with_an_existing_menu_truth_is_still_excluded_regardless_of_backoff`
→ split into three tests: recently-checked stays excluded, stale becomes
eligible, never-stamped becomes eligible). Extended the existing
materialized-success test to assert the new stamp. 5 net new/changed
tests in `tests/test_menu_worker.py`.

Also drafted `docs/privacy-policy.md` and `docs/terms-of-service.md` —
real content reflecting CRAVE's actual data flows (Supabase auth,
location use, R2 photo storage, Google Places/DeepSeek/Sentry as
third-party processors, content moderation, block/account-deletion
mechanics) rather than placeholder text. Explicitly flagged as not legal
advice and needing an actual lawyer's review plus filling in bracketed
placeholders (jurisdiction, contact email) before publishing — hosting
these at the URLs `settings.tsx` already links to (`crave.app/privacy`,
`/terms`) is still on the user, this only removes "start from a blank
page" as a blocker.

Verified: 555 backend tests passing (551 + 2 leaderboard + 3 net
menu_worker change, stable across repeated full-suite runs).

### Follow-up — live production check, and a throughput bump for menu_worker's growing backlog

First real production check since the OSM/Overture/staleness/blocking
work went live. Real numbers: 32,788 active places (up from 29,626 — real
catalog growth, almost entirely from OSM: 7,326 candidates found, 6,224
promoted, an 85% hit rate). Places with some source (website/Grubhub/menu
URL) grew 10,754 → 12,123. Menu coverage itself barely moved (738 → 761,
2.5% → 2.3%) — not a red flag, just discovery currently outpacing
extraction: `menu_worker` only processes up to 200 places per 10-minute
run, and the sourced-but-unchecked backlog (12,123 minus 761) is now
larger than before. Overture Maps showed **zero** candidates in
production — confirmed the pyarrow-missing issue has been silently
killing every run since deploy, not just failing to enrich; re-ran the
manual `pip install pyarrow` console workaround on the (also newly
resource-exhausted-then-restarted) container to unblock it again, same
known limitation as before (doesn't survive the next restart/redeploy).

Also checked photo coverage the same way, expecting it to mirror the
weak menu number — it doesn't. **43.5% of places have a visible primary
photo**, dramatically healthier than menus, because most photo coverage
comes from Google Places' readily-available photo data rather than
needing real extraction the way menus do. Caught and corrected my own
mid-query error here: initially reported "31,113 places never had an
image fetch attempted" as if it were a red flag — `Place.
image_fetch_attempts` turned out to only increment on *failure*
(confirmed by reading `image_worker.py` directly), not on every attempt,
so that number actually meant "never failed," which is expected for the
huge majority that just succeeded on the first try. Retracted that
framing before it was taken as a real problem.

Given the growing sourced-but-unchecked backlog, bumped `menu_worker.py`'s
throughput: `BATCH_SIZE` 25→40, `MAX_PLACES_PER_RUN` 200→300. Kept
moderate rather than maxed out — the scheduler runs embedded in the same
single process serving web requests (confirmed via deploy logs: no
separate worker service is actually deployed, despite one existing as an
option in the codebase), so a much larger jump risks competing with real
traffic rather than just working through the backlog faster. Pure config
change, no new tests needed; verified the full suite still passes (555,
unaffected).

### Follow-up — real device/simulator testing surfaced 3 app bugs; one confirmed and fixed (expired photo refs), two still open

User actually ran the app (`npx expo start` + iOS simulator) against the
live production API for the first time this session and shared real
screenshots. Three complaints, each checked against actual code/behavior
rather than assumed:

1. **"Pages blank ... no places hve photos"** — confirmed real. Read
   `app/api/v1/routes/image.py` (`proxy_image`), `src/utils/imageUrl.ts`,
   and `src/api/normalize.ts` (`resolveImageUrl`) end to end — all
   structurally correct (relative `/api/...` image paths are correctly
   resolved to the real API base, the proxy correctly streams Google's
   response and 404s as `"Image not found"` only when Google's own
   response isn't 200). Had the user hit a real production image URL
   directly in a browser to settle it either way: got back
   `{"detail":"Image not found"}` — proof the specific stored Google
   Places photo reference had expired (these are ephemeral/session-scoped
   by design on Google's side), not a bug in our proxy or in the RN
   `<Image>` component. Same "backlog outpaces worker throughput" shape
   already fixed for `menu_worker`, so applied the same fix here: bumped
   `ImageWorker().run(db=db, limit=...)` in `scheduler.py`'s
   `_job_image_ingestion()` from 50 → 100 (still under
   `image_worker.py`'s own `MAX_BATCH_SIZE = 200`). Verified: full backend
   suite passes (555, twice in a row, unaffected — this is a scheduler
   call-site config change only, no logic touched).

2. **"I cant sign in"** ("Safari can't open the page because the server
   can't be found" after tapping Continue with Apple/Google) — read
   `AuthSheet.tsx` in full; the OAuth code itself (`signInWithOAuth` →
   `WebBrowser.openAuthSessionAsync`, redirect URI via
   `AuthSession.makeRedirectUri({scheme:'crave'})`) looks structurally
   correct. That specific error is a DNS-resolution-level failure, most
   consistent with a **paused Supabase free-tier project** (auto-pauses
   after inactivity — and this app hadn't actually been run end-to-end
   before this session). Asked the user to check the Supabase dashboard
   for a "paused" banner and unpause if so — **not yet confirmed either
   way, still open**, not something fixable from here without seeing the
   dashboard.

3. **"we need regualr emails also"** — confirmed real, not a bug: there
   is no email/password sign-in/sign-up form anywhere in the codebase —
   `AuthSheet.tsx` only wires up Apple and Google OAuth. **Not yet
   built.**

("Menus arent there either" for the places shown matches the real 2.3%
menu coverage number above — expected given current backlog, not a
separate bug.)

### Follow-up — built email/password sign-in and sign-up

Closed the "we need regualr emails also" gap. `AuthSheet.tsx` previously
only had Apple/Google OAuth buttons; added a "Continue with email" option
below a divider that switches the sheet into an email/password form
(back chevron returns to the OAuth options), with a toggle between
sign-in and "create account" (sign-up) modes.

- Sign-in calls `supabase.auth.signInWithPassword`; sign-up calls
  `supabase.auth.signUp`. Neither needed any new plumbing to actually log
  the user in — `useAuthStore`'s existing `supabase.auth.onAuthStateChange`
  listener picks up the resulting session exactly the same way it already
  does for OAuth, and the existing username-claim gate
  (`app/profile-setup.tsx`, triggered from the profile tab when a user has
  no profile row yet) applies identically regardless of which auth method
  created the account — nothing else in the app is auth-method-aware.
- Handled the case Supabase's default project settings produce on sign-up
  (email confirmation required, so `signUp` returns no session): shows a
  toast telling the user to check their email and confirm, then switches
  the sheet back to sign-in mode rather than silently doing nothing.
- Added `humanizeAuthError()` to translate the handful of raw Supabase
  error strings users will actually hit ("Invalid login credentials",
  "already registered", password-too-short, unconfirmed email, rate
  limit) into actionable copy instead of showing Supabase's internal
  wording verbatim.
- Client-side validation only (real email format, 6+ char password) —
  Supabase enforces the authoritative rules server-side regardless.
- Explicitly **not** built here: a forgot-password / reset flow. That
  needs its own deep-link-handling screen (consuming a recovery-type
  token the same way `createSessionFromUrl` already consumes an OAuth
  token) — a real follow-up, not done as a silent gap, just kept out of
  this change to stay scoped to what was asked.

Verified: `npx tsc --noEmit` clean, full frontend Jest suite passes (82,
unaffected — no existing test file covers `AuthSheet.tsx` itself, so this
was also manually reasoned through against the existing OAuth code path
rather than caught by a new automated test). Backend untouched, no
re-run needed.

### Follow-up — search screen showed nothing below the 2-character query threshold

User reported "search doesnt wkork either nothing is popping up" — the
screenshot showed a single character typed ("K"). `search.tsx` only
fires a query once `debouncedQuery.length >= 2` (deliberate — avoids a
request per keystroke), but nothing else in the render tree covers the
gap below that: `showTrending` requires `query.length === 0`, and
`showNoResults`/results both require an actual completed search. Below 2
characters, the screen showed only the search bar with a totally blank
body — indistinguishable from broken. Added `showBelowThreshold` (`0 <
query.length < 2`) rendering a plain "Keep typing to search…" hint in
that gap. Also actively investigating a separate, real report from the
same message that the Map tab shows no pins at all, even after
selecting a specific city (ruling out the GPS/default-region fallback as
the cause) — still open, waiting on Metro console log output
(`[API] MAP_RAW` / `[MAP] FEATURES_LOADED`) to see the actual API
response before changing anything, since guessing here risks masking
the real cause.

Verified: `npx tsc --noEmit` clean, full frontend Jest suite passes (82,
unaffected — no test file covers this screen either).

### Follow-up — map showed zero pins in every city; root-caused via real device logs, not a guess

Got the actual Metro console output from the running app (real production
data — Feed and Search both loaded correctly, e.g. a 30-result "Kl" search
with real SF/Oakland places). The Map tab's own logs told the whole story:

```
[MAP] FEATURES_LOADED {"count": 0, "radiusKm": 1.0163933861884407, ...}
[MAP] FEATURES_LOADED {"count": 0, "radiusKm": 1.0163857800932163, ...}
```

Both actual fetches used a ~1km radius — nothing like the ~7km the app's
real `initialRegion` (0.08° delta) computes to, and this happened
regardless of which city was selected (confirmed live: still blank after
switching to a specific city, ruling out the GPS/default-location theory
first). Root cause: a known `react-native-maps`/iOS MapKit quirk — the
very first `onRegionChangeComplete` fired right after the MapView mounts
reports a bogus, heavily-zoomed-in transient region that has nothing to
do with the `initialRegion` prop, because the native view reports its
"settled" state before layout has actually finished applying the
requested region. `map.tsx`'s existing `programmaticMoveRef` guard only
covers events caused by *our own* `animateToRegion` calls (city switch,
cluster tap) — it does nothing for this native-internal one. That bogus
event's fetch starts after the mount effect's correct fetch, so it wins
`requestIdRef`'s race and silently clobbers the real (correct, non-empty)
results with an empty one — explaining why the map was blank in every
city, every time.

Fix: added `hasHandledFirstRegionRef`, and `handleRegionChangeComplete`
now unconditionally ignores the very first invocation per mount (no
`setMapRegion`, no fetch) before falling through to the existing
programmatic-move / debounce-and-fetch logic. The initial real load is
already handled correctly by the separate mount effect, so nothing is
lost by ignoring this one spurious event.

Verified: `npx tsc --noEmit` clean, full frontend Jest suite passes (82,
unaffected — no test file exercises `MapView` callbacks). Have not yet
had the user re-test in the simulator to confirm pins now render — that
confirmation is still outstanding.

### Follow-up — map still showed "Could not load places" after the fix above; researched against react-native-maps' own issue history and applied the library's documented fix

The `hasHandledFirstRegionRef` fix above stopped the bogus first event from
clobbering real results, but the user then hit a *different* symptom on
re-test: an actual "Could not load places" error banner (a real fetch
failure, not just an empty result). First added real error logging
(`[MAP] LOAD_FAILED` — the catch handler was previously completely
silent, logging nothing about the axios error), since guessing at the
cause without knowing whether it was a timeout, a 4xx, or a 5xx would
just be more speculation.

In parallel, per a direct request to compare this codebase against real
working map implementations rather than keep guessing: researched
`react-native-maps`'s own GitHub issue tracker. `initialRegion` failing
to be honored correctly on iOS turns out to be a *years-long, recurring,
well-documented* bug class in that library specifically (issues #1507,
#3212, #4244, #4420, #5645 — spanning 2017 through 2025), and the
standard, community-endorsed fix real projects use is consistent across
all of them: don't trust `initialRegion` alone — use the `onMapReady`
callback to explicitly `animateToRegion()` once the native view has
actually finished initializing.

Checking our own code against that pattern found the real gap: `map.tsx`
already had an effect that calls `animateToRegion` on mount (keyed off
`[selectedCity?.id, mapLat, mapLng]`), but that effect races the native
view's own initialization — `mapRef.current` can still be unset when it
runs, so the correction silently no-ops on the very first mount (later
city switches work fine because by then the map has long since been
ready). This explains why our home-grown "ignore the first event" patch
only fixed the *fetch* — the underlying visual region itself was likely
still wrong underneath, just no longer driving a bad request.

Added `onMapReady={handleMapReady}`, which redoes the same
correction (`programmaticMoveRef` + `animateToRegion`) at the moment the
native view guarantees it's actually ready — the fix the library's own
issue tracker prescribes for exactly this failure mode, not a
CRAVE-specific guess.

Also added a same-session, lower-priority gap noticed during the
research pass: the "Could not load places" banner was static text with
no retry action, unlike the retry-on-failure pattern seen in comparable
map implementations. Added a `lastAttemptRef` (tracks the most recent
attempted lat/lng/radius regardless of success/failure, unlike
`lastFetchCoverageRef` which only updates on success) and made the
banner tappable to retry that exact request via `handleRetryMap`.

Verified: `npx tsc --noEmit` clean, full frontend Jest suite passes (82).
Still waiting on the user to reproduce once more with all of this live —
if `onMapReady` fully addresses it, pins should now render on first load
without any pan needed; if "Could not load places" still appears, the
`[MAP] LOAD_FAILED` log added earlier will finally show the real HTTP
status/error instead of a guess.

### Follow-up — built the first real automated test coverage for map.tsx, reproducing the exact production bug sequence

Given there was no way to hand a real iOS simulator to verify the
`onMapReady` fix, built an actual regression test instead of just
asserting the fix "should" work: `app/(tabs)/map.test.tsx`, using
`@testing-library/react-native` against a manual mock of
`react-native-maps` (`__mocks__/react-native-maps.tsx` — a `MapView`
stand-in that captures whatever props it was given and exposes an
`animateToRegion` spy through the ref) so the exact event sequence seen
in production could be driven directly: mount → a simulated spurious
native `onRegionChangeComplete` (same ~1km-radius shape logged live) →
`onMapReady` → a genuine user pan.

Four tests, all passing, each proving one specific claim rather than
just re-describing the code:
- the spurious first event does not trigger a second fetch or clobber
  the real (already-loaded) results,
- `onMapReady` calls `animateToRegion` with the correct city region,
- a genuine pan *after* `onMapReady` still triggers a real fetch with
  the right lat/lng (proving the fix doesn't accidentally suppress real
  panning),
- the retryable error banner (added in the same change) actually shows
  on failure and re-issues the identical request on tap.

Also had to add `__mocks__/@react-native-async-storage/async-storage.js`
(pointing at that package's own officially-documented jest mock) — this
was previously not needed because no test imported anything that
transitively pulled in the real Supabase client (which requires
AsyncStorage) until this one did via `cityStore`. This is a repo-wide
enabler, not map-specific — any future test that touches a Zustand store
backed by `persist`/AsyncStorage benefits from it too.

Verified: `npx tsc --noEmit` clean, full frontend Jest suite passes (86 —
82 previous + 4 new), stable across a second run.

### Follow-up — the new test file crashed the actual running app; moved it out of app/

Self-inflicted regression: expo-router treats every file inside `app/`
as a route candidate, so placing `map.test.tsx` in `app/(tabs)/`
alongside the real route files meant Metro bundled it straight into the
running app. It crashed instantly with `ReferenceError: Property 'jest'
doesn't exist` — the mock file's `jest.fn()` calls only exist inside the
Jest runner, not in a real bundle — confirmed live via a red error
screen in the user's simulator with that exact message. Fixed by moving
the test to a new top-level `__tests__/` directory (sibling to `app/`,
outside expo-router's scan root) and updating its relative imports
accordingly; no test logic changed. `__mocks__/react-native-maps.tsx`
was never affected (it already lived outside `app/`).

Verified: `npx tsc --noEmit` clean, full suite passes (86, same count,
same assertions — only import paths changed).

### Follow-up — the real root cause of "Could not load places": map's primary-image lookup was the one list surface never converted to the bulk pattern, and it was timing out in production

After the `onMapReady` fix landed, the user reproduced again with a fresh
build and got the actual signal needed:

```
[MAP] LOAD_FAILED {"lat": 37.7652, "lng": -122.2416, "message": "timeout
of 25000ms exceeded", "radiusKm": 7.12448, "status": undefined}
```

Two important things this confirmed: `radiusKm: 7.12448` is the correct
~7km region (proving `onMapReady` genuinely fixed the earlier ~1km-region
bug), and `status: undefined` with a client-side timeout means the
backend never responded at all in 25s — a real slow-query problem, not
empty results or a crash. Feed, Search, Trending, and Detail all loaded
normally in the same session, narrowing it to something map-specific.

Root cause, found by comparing `map_query.py` against every other list
surface: `fetch_places_for_map`'s primary-image lookup was a **correlated
scalar subquery embedded directly in the main SELECT** — one extra
filtered/sorted lookup against `place_images` for every one of up to
`limit` (default 250, max 1000) rows in the bounding-box result. Every
other list surface (feed, search) resolves this the same way categories
already are here (see the existing "avoids N+1 per pin" comment on the
categories lookup two lines above it) — as a single separate bulk query
(`get_primary_image_urls_bulk`: one `place_id IN (...)` query, grouped in
Python) specifically to avoid this exact cost. `map_query.py` was the one
surface that never got that treatment; it even had its own third,
inline-duplicated copy of the same subquery logic that
`place_image_visibility_query.py` already exposes as a shared helper
explicitly documented as "for use in larger queries, e.g. map" — that
helper existed and was never actually wired up here.

Fixed by dropping the per-row subquery from the main query entirely and
adding a `get_primary_image_urls_bulk` call alongside the existing
categories bulk lookup, merged into the response the same way categories
already are. Also removed the now-redundant second `_to_proxy_url` call
in the GeoJSON wrapper (the bulk helper already returns proxy-formatted
URLs) — confirmed `_to_proxy_url` is idempotent on an already-proxied URL
either way, so this was never a correctness bug, just dead work.

No test previously exercised `fetch_places_for_map` against a real DB
with actual `PlaceImage` rows at all (the existing `tests/map/
test_map_geojson.py` only covers the GeoJSON transform layer given
pre-built data, and the tier-threshold helpers) — a real, pre-existing
gap independent of this change. Added `tests/test_map_query.py`: a place
with a visible primary image resolves it correctly, a place whose only
primary image is hidden gets `None` (visibility filtering preserved), two
places in the same result set each get their own correct image with no
cross-contamination from the bulk lookup (the specific failure mode a
careless bulk-query rewrite could introduce), and a place with no image
at all gets `None` rather than erroring.

Verified: full backend suite passes (559 — 555 previous + 4 new), stable
across two consecutive runs.

### Follow-up — Feed crashed with a React "duplicate key" error mid-session, unrelated to the map

Live-confirmed via the same testing session: `app/(tabs)/index.tsx`'s
`FlatList` threw "Encountered two children with the same key" for a real
place id appearing in both an already-loaded page and the next one
fetched. Root cause: the feed paginates by 1-indexed page number against
a plain offset/limit query ordered by `rank_score`, not a stable cursor.
The discovery pipeline runs every 5 minutes and (especially after this
session's own throughput bumps) keeps inserting new places between page
fetches — each insertion shifts every later page's offset window, so a
place already shown on an earlier page can reappear inside a
subsequently-fetched page's window. A real fix (keyset/cursor
pagination) is a bigger backend change than warranted mid-session;
de-duplicated the flattened `places` list by `id` instead, which
directly eliminates the actual user-visible crash regardless of why a
duplicate ID showed up.

Verified: `npx tsc --noEmit` clean, full frontend suite passes (86,
unaffected — no existing test covers this screen). Backend untouched,
no re-run needed.

### Follow-up — audited the Craves/share feature against Biter (a direct competitor), closed the "sharing ≠ saving" gap

Asked to compare CRAVE's Craves feature end-to-end against "Biter" (a
real competitor app whose core hook is: save a TikTok/Instagram/YouTube
food video, and it auto-plots that spot onto your personal map). Full
audit found the backend matching pipeline
(`share_parser_worker.py`) already genuinely sophisticated — real oEmbed
caption/thumbnail/author data for TikTok/YouTube, SSRF-safe HTML-scrape
fallback for plain web links, fuzzy place matching, retry/backoff, and
unmatched shares feed the discovery-candidate pipeline instead of
dead-ending. Frontend has a real paste-a-link entry point
(`ShareLinkSheet.tsx`, in the Craves tab) and matched shares render as
"seen on TikTok/@author" social-proof cards on the place detail page.

The one *closeable-today* gap found: sharing a link that matched a real
place did nothing for the person who shared it beyond a status change on
their own pending item — `CraveItem` (the share pipeline) and
`HitlistSave` (the actual personal-saves table backing `GET/POST
/api/v1/saves`) were completely disconnected. You'd have to separately
go find and save the place yourself after sharing it, unlike Biter's
"share it and it's on your map" behavior.

Fixed in `share_parser_worker.py`'s matched branch: when a share matches
a place and `submitted_by` is set, it now also creates a `HitlistSave`
row for that user — same `"save:{user_id}:{place_id}"` dedup_key
convention `saves.py`'s manual `create_save` already uses, so the result
is indistinguishable from a manual save (shows up in `GET /saves`, can
be un-saved via `DELETE /saves/{place_id}`). Idempotent (checks for an
existing save first) and isolated in its own try/except + commit so a
failure here can never affect the "matched" status that's already
committed. Added `tests/test_share_parser_auto_save.py` (4 tests): a
matched share creates the save, an already-existing save isn't
duplicated, an unmatched share creates no save, and a legacy item with
no `submitted_by` doesn't error.

Bigger gaps found in the same audit, intentionally left for a joint
planning pass rather than built solo:
- **No native iOS Share Sheet** — sharing today is copy-link-then-paste,
  not sharing directly from within TikTok/Instagram's own share menu.
  Needs `expo-share-intent` and ejecting off Expo Go for a native
  rebuild — real infra work, not a quick fix.
- **No personal-saves layer on the Map tab** — Map only ever shows the
  global catalog; there's no way to see just your own saved/shared spots
  plotted on their own map (Biter's core "custom food map" feature).
- **No proximity alerts** — zero push-notification/geofencing
  infrastructure exists anywhere in the app.

Verified: full backend suite passes (563 — 559 previous + 4 new), stable
across two consecutive runs. Frontend untouched, no re-run needed.

### Follow-up — built the "friend rating" feature (Beli's other core hook), audited Beli directly too

Asked to also check Beli (the other named competitor) and close any more
small, self-contained gaps, leaving bigger ones for a joint planning
pass. Beli's advertised feature set: forced-order pairwise ranking (CRAVE
already has this — the binary-insertion comparison algorithm built
earlier this session), a friend-rating average per place, personalized
"prediction score" recommendations based on ranking history + friends'
taste, gamified streaks/yearly goals, an interactive personal map of
your own ranked places, and "Taste Profile" stats (total eaten, favorite
cuisines, top cities).

One of these was small and self-contained enough to build now: **friend
ratings on place detail**. CRAVE already had 100% of the underlying data
(`PlaceRanking` + the follow graph) but never surfaced it — the place
detail screen had no notion of "your friends" at all. Also found, while
scoping this, that the "unlock recommendations" progress card on the
profile screen (`rankScore.ts`'s `RECOMMENDATION_THRESHOLD`/
`recommendationProgress`) has been a dead promise — grep across the
whole app turns up literally zero code implementing an actual
recommendation feed once "unlocked." That's real, but a whole missing
subsystem (needs a taste-similarity/prediction algorithm), not a
same-day fix — added to the big list below rather than attempted here.

Built:
- `app/services/social/friend_rankings_service.py` (new) —
  `get_friend_rankings_for_place`: rankings of a place by people the
  caller follows, best-to-worst, block-safe for free (a blocked user can
  never appear in `list_following`'s result — same reasoning
  `leaderboard_service`'s `among="friends"` branch already relies on).
- `GET /api/v1/place/{place_id}/friends` (new route in
  `place_detail_router.py`) — deliberately a **separate** endpoint from
  `GET /place/{place_id}`, not a field folded into it: that response is
  cached globally by `place_id` alone, shared across every viewer —
  adding per-viewer follow-graph data there would either leak one user's
  friend rankings to another through the shared cache, or force
  disabling that cache entirely. This one is never cached and always
  scoped to the caller's own follow graph, same pattern
  `GET /craves/for-place/{id}`'s separate "seen on social" call already
  uses for the identical reason.
- Frontend: `fetchFriendRankings` (`src/api/social.ts`) and a "Ranked by
  N friends" horizontal card row on the place detail screen (avatar,
  username, tier label/color reusing the already-built
  `TIER_LABELS`/`tierColor` utilities from the ranking flow), fetched
  only when signed in, tapping a friend opens their profile.
- `tests/test_friend_rankings_service.py` (4 tests): rankings ordered
  best-first, a non-followed user's ranking is excluded, following
  nobody returns empty, and a followed user who hasn't ranked the place
  doesn't appear.

Caught and fixed a real test-isolation bug while adding this: the new
test file's `Place` rows (rank_score defaults to 0.0, zero images) had
no teardown, and depending on file-run order they leaked into
`test_image_worker_starvation.py`'s own *unscoped* query — confirmed via
full-suite runs that it flaked specifically because ImageWorker's
starvation-reserve logic deliberately goes looking for exactly that
shape of neglected place. Fixed by adding proper create/teardown
tracking to the new test's `db` fixture (mirrors the cleanup pattern
`test_share_parser_worker_retry.py`'s `make_item` fixture already uses).

Verified: full backend suite passes (567 — 563 previous + 4 new), stable
across two consecutive fresh-DB runs. Frontend: `npx tsc --noEmit`
clean, full suite passes (86, unaffected).

**Bigger gaps found across the Biter + Beli audit, left for a joint
planning pass rather than built solo** (see the earlier entry above for
the Biter-specific ones):
- **No personalized recommendation engine** — the profile screen
  promises one ("rank 15+ places to unlock recommendations") but nothing
  is actually built behind that promise. Beli computes this from ranking
  history + friends' taste; needs real algorithm design.
- **No gamification** (streaks, yearly goals) — Beli's Duolingo-style
  streak tracking and "rank N places in 2026" goals. Needs product
  decisions (what counts as a streak day, notification hooks) as much as
  code.
- **No "Taste Profile" stats page** — total places ranked, favorite
  cuisine, top city, etc. Straightforward aggregation over data CRAVE
  already has, but a new screen/design, not a one-line fix.
- (Still open from the Biter audit) native iOS Share Sheet, a
  personal-saves layer on the Map tab, and proximity alerts.

### Follow-up — full research pass on all 6 remaining big gaps, then built the "my saved places" Map layer (item #1 of the agreed build order)

Researched each remaining gap against real sources (library docs, Apple's
own guidelines, established algorithm patterns) rather than guessing, then
asked the user to resolve the decisions that actually block work:

- **Native share sheet** (`expo-share-intent`) — confirmed via its own
  docs: requires ejecting off Expo Go entirely (custom dev client / EAS
  Build, `expo prebuild`), an Apple Developer account ($99/yr), and an
  App Group entitlement. User doesn't have the Apple Developer account
  yet and chose to hold off on ejecting until other work is done first.
- **Proximity alerts** — researched Apple's Guideline 5.1.1 and
  confirmed geofencing is one of the accepted justified uses for
  "Always" location (user is fine asking for it), but background
  geofencing via `expo-task-manager` also effectively requires a
  development build, same as the share sheet — a finding that wasn't
  obvious going in and changes sequencing: this now groups with the
  share sheet as a second, later push, not something to build alongside
  the others now.
- **Personalized recommendations** — confirmed user-based collaborative
  filtering (similarity between users' `PlaceRanking` rows) is the
  standard, lightweight approach — no ML infra needed at CRAVE's scale.
- **Gamification (streaks)** — confirmed Duolingo's own documented
  pattern: server is the source of truth (never trust device time),
  compare by calendar day in the user's IANA timezone (not raw hour
  math — the most common place this gets built wrong), plus a "streak
  freeze" concept.
- Agreed build order (least-rework-first): personal-saves map layer →
  Taste Profile stats → personalized recommendations → gamification, all
  buildable in the current Expo Go workflow; share sheet + proximity
  alerts bundled together later as their own dedicated push once the
  Apple Developer account exists and ejecting is worth doing.

Built the first item: **the personal-saves Map layer.**

- `app/services/query/saved_places_map_query.py` (new) —
  `get_saved_places_geojson`: every place the user has saved
  (`HitlistSave`, `dedup_key="save:{user_id}:{place_id}"`), returned in
  full rather than viewport-scoped like the global map query — a
  personal list is small enough to just fetch entirely and let the
  client fit the map to it. Every feature's `tier` is fixed to
  `"default"` rather than reusing the global map query's percentile
  logic, since a percentile computed over a handful of personal saves
  wouldn't mean anything (your one save would trivially be "elite").
- `GET /api/v1/saves/map` (new route in `saves.py`) — GeoJSON-shaped,
  reuses the same schema as the global map endpoint for frontend code
  reuse.
- Frontend: `fetchSavedPlacesGeoJSON` (`src/api/map.ts`), and a new
  bookmark-icon toggle button on the Map tab (only visible when signed
  in) that switches between the existing global-catalog view and this
  new "my places" view. Switching to saved mode fits the map to all
  saved pins (`fitToCoordinates` for 2+, a direct region for exactly 1);
  the existing city-based fetch/pan/recenter effects are all guarded to
  no-op while in saved mode, and re-activate cleanly on switching back.
- `tests/test_saved_places_map_query.py` (4 tests): returns saved
  places as GeoJSON, excludes other users' saves, empty when nothing's
  saved, and excludes non-place-backed hitlist rows (raw/unresolved
  wishlist entries, or craves-flow entries that aren't dedup_key
  "save:"-prefixed).
- `__tests__/map.test.tsx` (+4 tests): toggle hidden when signed out,
  switching to saved mode fetches and fits bounds without firing a
  viewport fetch, panning while in saved mode fetches nothing, switching
  back to city mode re-fetches the global catalog. Caught and fixed a
  real test-only bug while writing these: the `useAuthStore` mock
  created a fresh `{ user: {...} }` object on every call, which made
  React see the `user` dependency as "changed" every render and spun the
  saved-mode effect into an infinite loop — confirmed via a genuinely
  hung test run, not a guess. Fixed by giving the mock a single stable
  object reference (matching how the real Zustand hook behaves — it
  only returns a new reference when the store's state actually
  changes). Not a bug in `map.tsx` itself.

Verified: backend suite passes (571 — 567 previous + 4 new), stable
across two runs. Frontend: `npx tsc --noEmit` clean, full suite passes
(90 — 86 previous + 4 new).

### Follow-up — built Taste Profile (item #2 of the agreed order), after a proper research pass

Asked to research this "perfectly" rather than guess at a design.
Cross-referenced across three independent sources (today.com, hercampus,
and a general search) to confirm Beli's actual Taste Profile shows:
total restaurants ranked, favorite cuisines, top/highest-ranked cities,
a percentile rank among other diners, and a "Match Score" taste-
compatibility feature with a specific friend. Surfaced the one real
design ambiguity before building rather than guessing: Match Score needs
the same user-similarity algorithm as the next item in the agreed order
(personalized recommendations) — asked the user, who left it to my
judgment; folded it into the recommendations work instead of duplicating
the computation here, keeping this screen to pure stats.

Also asked (rather than assume) the three other real forks: percentile
scope (chose global across all users, not city-scoped, since CRAVE's
current user base is too small for a per-city percentile to mean
anything — revisit once there's more data per city), placement (own
screen, matching the existing `/leaderboard`, `/friends-feed` pattern
rather than bloating profile.tsx), and whether a friend's Taste Profile
should be viewable too (yes — so the backend endpoint and screen both
take an arbitrary `user_id`, not just "me").

Built:
- `app/services/social/taste_profile_service.py` (new) —
  `get_taste_profile`: total ranked, tier breakdown, favorite cuisine
  (computed from "liked"-tier places, falling back to all ranked places
  only if none are liked yet — a cuisine that's only in a "disliked"
  place isn't your favorite; also excludes generic categories like
  "Restaurant"/"Bar" the same way `place_detail_router.py` already
  does), top city (most ranked places in), and percentile (global,
  computed against every other user who's ranked at least one place).
- `GET /api/v1/profile/{user_id}/taste` (new route in `profile.py`) —
  gated on the same `is_public` check as the existing public-profile
  route, for consistency with whatever visibility the person already
  chose. Block enforcement stays client-side, same convention
  `user/[id].tsx` already uses via `GET /blocks/status`.
- Frontend: `fetchTasteProfile` (`src/api/social.ts`) and a new
  `app/taste-profile/[userId].tsx` screen (stat tiles, tier breakdown,
  favorite-cuisine and top-city cards), linked from both your own
  profile (`profile.tsx`'s existing Friends/Leaderboard link row) and a
  friend's profile (`user/[id].tsx`, right below the ranked-list
  headline).
- `tests/test_taste_profile_service.py` (7 tests): totals/tier counts,
  favorite cuisine prefers liked places, falls back correctly with no
  likes yet, excludes generic categories, top city is the city with the
  most ranked places, percentile reflects real standing among other
  users, and everything is `None`/zero for a user who hasn't ranked
  anything.

Verified: backend suite passes (578 — 571 previous + 7 new), stable
across two runs. Frontend: `npx tsc --noEmit` clean, full suite passes
(90, unaffected — no dedicated test for the new screen itself, same as
other similarly-scoped screen additions this session; covered by the
service-level tests plus a clean typecheck).

### Follow-up — audited every remaining list-surface route for the same primary-image N+1 pattern found in map_query.py; one dead-code cleanup found, no other bugs

Asked to keep looking for anything else to improve. Since `map_query.py`
turned out to have a real production timeout from a per-row correlated
subquery instead of the shared `get_primary_image_urls_bulk` bulk
lookup, audited every other route/service file that touches
`primary_image` to rule out the same bug elsewhere:
`rankings.py`, `search.py`, `trending.py`, `place_detail_router.py`,
`places.py`, `feed_social.py`, `saves.py`, `discovery_places.py`,
`places_query.py`, `place_detail_query.py`. All the list-returning ones
(`rankings.py`, `search.py`, `trending.py`, `feed_social.py`,
`places_query.py`) already call `get_primary_image_urls_bulk` correctly;
`place_detail_query.py` only ever resolves one place at a time (not a
list), so `images[0] if images else None` there was never an N+1 risk.

The one thing this turned up: `discovery_places.py` had its own
`get_primary_image(db, place_id)` — a single-place, non-bulk helper with
no visibility filtering — that was never imported or called anywhere in
`app/` or `tests/` (confirmed via a repo-wide grep for both the function
name and the module's other exports). It predates the shared
`place_image_visibility_query.py` helpers and was fully superseded by
them; nothing depended on it. Removed the dead function and its
now-unused `PlaceImage` import.

Verified: full backend suite passes (578, unchanged — nothing referenced
the removed function, so no test count change), stable across two runs.

### Personalized recommendations + Match Score (item #3 of the agreed roadmap, closes Beli's "prediction score" gap)

Built the last big deferred item from the earlier research pass:
user-based collaborative filtering over `PlaceRanking` rows, confirmed
via research as the right level of sophistication for CRAVE's current
scale (no new ML infra). Also builds Beli's "Match Score" — deliberately
deferred from the Taste Profile work specifically so it could reuse this
same similarity computation instead of a second bespoke one.

Algorithm (`app/services/social/recommendation_service.py`, new):
for user U, build their `{place_id: rank_score}` vector, find every
other non-blocked user who ranked at least 2 of the same places
(`MIN_SHARED_PLACES` — below that, "similarity" is noise: two users who
share exactly one ranked place agree "perfectly" by construction), score
them by cosine similarity restricted to the shared places, then weight
every place a similar user ranked (that U hasn't already ranked or
saved) by `similarity * their_rank_score` and sum across similar users.
Cold start (no ranking history yet, or genuinely no similar users found)
falls back to the highest-`rank_score` active places U hasn't
interacted with yet — never personalized, but never an empty screen.
`get_match_score(user_a, user_b)` reuses the identical cosine similarity
computation and returns it directly as a 0–100 percentage (rank_score is
always non-negative, so the general `[-1, 1]` cosine range is already
bounded to `[0, 1]` in practice here) — `None` if they haven't ranked
enough of the same places yet for the number to mean anything, which
callers must treat as "not enough data," not "0% match."

- `GET /api/v1/recommendations` (new route, `recommendations.py`) —
  same `PlaceOut`/`PlacesResponse` shape and bulk-image-lookup pattern as
  `trending.py`, specifically so the frontend could reuse its existing
  place-list rendering rather than a bespoke response shape. Requires
  auth (personalized, not just public data).
- `GET /api/v1/profile/{user_id}/taste` now also returns `match_score`
  when the viewer is signed in and looking at someone else's profile.
  This needed the taste route (previously fully anonymous/public) to
  know the *viewer's* identity without requiring sign-in to view a
  public profile at all — added `get_current_user_id_optional` to
  `app/core/user_auth.py` (returns `None` instead of raising 401 on a
  missing/invalid token) rather than making the whole route auth-required.
- Frontend: `fetchRecommendations` (`src/api/places.ts`),
  `useRecommendations` hook (same generation-ref stale-response guard
  shape as `useTrending`'s, keyed on the signed-in user instead of the
  selected city). `TrendingStrip` gained an optional `heading` prop
  (default `"TRENDING"`) so the exact same component renders a
  "RECOMMENDED FOR YOU" strip on the feed (`index.tsx`, shown only when
  signed in, right above the existing trending strip) without
  duplicating its styles. `taste-profile/[userId].tsx` gained a third
  hero tile showing `match_score` as "`N`% taste match" — only rendered
  on someone else's profile, never your own.
- `tests/test_recommendation_service.py` (8 tests): cold start ranks by
  real `rank_score`; cold start excludes already-ranked/saved places; a
  place liked by a genuinely similar user (2+ shared places) gets
  recommended; a single shared place is *not* enough to count as similar
  (verified by confirming a place with a real intrinsic rank_score
  advantage still outranks a "boosted" pick, rather than asserting
  absence outright — the shared test DB isn't isolated across files, so
  a bare non-membership check would be sensitive to ambient seeded
  data); a blocked user's ratings are excluded from similarity by the
  same discriminating pattern; Match Score is `None` below the shared-
  places threshold, high (≥95) for closely-aligned tastes, and `None`
  for comparing a user against themselves.

Verified: backend suite passes (586 — 578 previous + 8 new), stable
across two runs. Frontend: `npx tsc --noEmit` clean, full Jest suite
passes (90, unaffected — no dedicated test for the new hook/strip
itself, same convention as other similarly-scoped UI additions this
session; covered by the service-level tests plus a clean typecheck).

### Daily streak gamification (item #4, last of the agreed roadmap)

Asked what should count as a "streak day" before building this one,
since it's a real product decision, not an implementation detail — the
answer was "not sure just yet." Built it so that decision stays cheap to
change later: `record_activity()` is called from a single place (the
app's root layout, on open/foreground) with the loosest possible
trigger for now (just having the app open), so swapping to a stricter
definition (e.g. "only counts if you ranked a place that day") later
only means changing *where* it's called from, not the streak math
itself.

Followed Duolingo's own documented pattern (confirmed via research):
the server is the source of truth for the current instant
(`datetime.now(UTC)`), never the device clock, but continuity is judged
by *calendar day*, which only means something relative to a timezone —
so the client sends its current IANA timezone name (e.g.
`Intl.DateTimeFormat().resolvedOptions().timeZone`, built into Hermes,
no new native dependency needed) and the server converts its own UTC
instant into that timezone to get "today." An unrecognized/garbled
timezone string falls back to UTC rather than erroring. No "streak
freeze" grace mechanic yet (out of scope for this pass) — a missed day
just resets the current streak to 1 on the next activity, though
`longest_streak` is preserved.

- `app/db/models/user_streak.py` (new) + migration
  `z1a2b3c4d5e6_add_user_streaks_table.py` — one row per user:
  `current_streak`, `longest_streak`, `last_active_date` (a calendar
  date, not a timestamp).
- `app/services/social/streak_service.py` (new) — `record_activity`
  (the day-boundary math: same day is a no-op, +1 day increments, >1 day
  gap resets to 1, and a negative gap — e.g. an implausible backward
  timezone jump — never moves the stored state backward, guarding
  against replaying activity into the past) and `get_streak` (read-only).
- `GET /api/v1/streak/me` (read, no side effect) and `POST
  /api/v1/streak/ping` (idempotent per calendar day) — new
  `streak.py` route.
- Frontend: `src/api/streak.ts` (`fetchMyStreak`, `pingStreak` — the
  latter reads the device's IANA timezone via `Intl`). Wired into
  `app/_layout.tsx`: pings once when the signed-in user becomes known,
  and again on every `AppState` transition back to `'active'` (covers
  the common case of backgrounding the app and reopening it the next
  day without a full remount) — best-effort, a failed ping is never
  user-visible. `profile.tsx` shows a 4th stat tile ("N day streak" with
  a flame icon) alongside ranked/followers/following, only once
  `current_streak > 0` (skips a discouraging "0 day streak" before the
  first ping has resolved).
- Also fixed stale copy this touched: `profile.tsx`'s "unlock
  recommendations" card still said ranking below 15 places meant "there
  isn't enough signal" and recommendations were locked — no longer true
  now that the recommendations feature (previous entry) always shows
  something via its cold-start fallback. Reworded to say what's actually
  true: below the threshold, "Recommended for you" shows top-rated picks
  rather than a personalized match.
- `tests/test_streak_service.py` (8 tests): first-ever ping starts a
  streak of 1; a same-day repeat is a no-op; a 1-day gap increments;
  a >1-day gap resets current_streak but preserves longest_streak; the
  boundary is calendar-day-based, not raw elapsed hours (the specific
  bug class this whole feature is designed to avoid); an implausible
  backward timezone jump never moves the streak backward; an
  unrecognized timezone name falls back to UTC instead of erroring; a
  user with no history reads as all zeros. `tests/test_streak_routes.py`
  (4 tests): the route wiring itself — GET has no side effect, POST
  records and returns the new state, a missing timezone in the request
  body falls back to UTC.

Verified: backend suite passes (598 — 586 previous + 12 new), stable
across two runs. Frontend: `npx tsc --noEmit` clean, full Jest suite
passes (90, unaffected — no dedicated test for `_layout.tsx`'s
AppState-driven ping effect, consistent with this session's convention
for similarly-scoped root-level wiring; covered by the service/route
tests plus a clean typecheck).

### Follow-up — live-reported bug: search only searched the selected city, missing a real match entirely

User reported searching "Thai me" while "Alameda" was selected returned
"No results," even though the place exists (just not in Alameda). Root
cause was two-layered:

1. `app/(tabs)/search.tsx` always sent `city_id: selectedCity?.id` to
   `/api/v1/search` whenever a city was selected — even though the
   backend route's own docstring already says `city_id` is optional,
   "omit for global search." The frontend was the one forcing a hard
   city scope on every search; a real match outside that one city was
   filtered out before it could ever be found.
2. Even fixing that isn't enough on its own: `search_query.py`'s SQL
   query ordered strictly by `rank_score DESC` before applying `LIMIT`.
   A real, nearby match with a modest `rank_score` can lose to unrelated,
   higher-ranked places in *other* cities and never even make it into
   the fetched page — `search_ranker.py`'s post-fetch proximity re-sort
   can't rescue a match that was never fetched in the first place, since
   it only reorders whatever page `rank_score` already selected.

Fixed both: `search.tsx` no longer sends `city_id` at all (global search
is now the only mode). `search_query.py::search_places` now orders the
SQL query itself by squared distance first (when the caller has a
location), rank_score only breaking ties among similarly-distant
results — guaranteeing a real nearby match is never crowded out of the
fetch window regardless of how it compares nationally. A place with no
coordinates sorts after every real distance via a large sentinel value
(avoids relying on dialect-specific `NULLS LAST` support, since the test
suite runs on SQLite but production is Postgres). The "Searching in
{city}" caption was also misleading now that search isn't city-scoped —
changed to "Searching everywhere, nearest first" when location is
available.

`tests/test_search_query.py` (new, 5 tests — this file had zero prior
coverage): a global search finds a match outside the "selected" city; a
nearby lower-`rank_score` match still outranks several distant
higher-`rank_score` ones under a small `limit` (the specific failure
mode a naive post-fetch-only re-rank can't fix); no location falls back
to the original `rank_score` ordering; a place with no coordinates still
appears, sorted last; an explicitly-passed `city_id` still filters
correctly (the parameter still exists for a future explicit "search in
this city" control — only the frontend's automatic use of it was
removed).

Verified: backend suite passes (603 — 598 previous + 5 new), stable
across two runs. Frontend: `npx tsc --noEmit` clean, full Jest suite
passes (90, unaffected).

### Follow-up — user reported the map fix "never worked" after 50+ pushes; added a way to actually verify deployment instead of asserting it

Pushed back on with a pasted Metro log showing both the exact
`jest.fn()`-in-bundle crash (fixed in `5ae90eb`) and the exact
`timeout of 25000ms exceeded` map error (fixed in `5ba2142`) happening
*together* — which is only possible on a build older than both fixes.
The `git pull` output right above it confirmed this directly: `Updating
8bc9697..fd4690d` — their local branch was only catching up to a commit
several pushes before either fix. Reasonable pushback, though: after
being told "should be fixed" multiple times, repeating that assurance
again isn't useful, and this session has no way to independently query
their live Railway deployment or production DB to confirm what's
actually running.

Rather than assert it a third time, added a real, self-serve way to
settle it: `GET /api/v1/debug/version` (new, unauthenticated — a git SHA
isn't sensitive) returns `RAILWAY_GIT_COMMIT_SHA` (which Railway sets
automatically on every GitHub-integration deploy), falling back to a
local `git rev-parse HEAD` when that env var isn't set (e.g. running
locally, not on Railway). Comparing this endpoint's `commit` field
against the branch tip's actual SHA after a deploy answers "is the code
I think shipped actually running" directly, without digging through the
Railway dashboard or trusting an assurance.

Also closed a real debugging gap this exposed: `map.tsx`'s success-path
log (`[MAP] FEATURES_LOADED`) only logged `count`/`radiusKm`/`sample` —
a *successful* response with zero features (a real, distinct case from
a timeout, also seen in this session's pasted log) gave no way to tell
what `lat`/`lng`/`city_id` were actually queried. Added them to match
the failure-path log, which already included them.

`tests/test_debug_routes.py` (+2 tests): `/version` reports
`RAILWAY_GIT_COMMIT_SHA` and `RAILWAY_ENVIRONMENT_NAME` when set, and
never requires the API key (unlike `/sentry-test`, gated deliberately
since it's a manual trigger, not a passive diagnostic).

Verified: backend suite passes (605 — 603 previous + 2 new), stable
across two runs. Frontend: `npx tsc --noEmit` clean, full Jest suite
passes (90, unaffected).

**Still open**: whether the map's actual timeout is fixed in production
is not yet confirmed — waiting on the user to redeploy, then compare
`GET /api/v1/debug/version`'s `commit` against `git rev-parse HEAD` on
this branch, and re-test with the now-more-complete `[MAP]
FEATURES_LOADED` / `[MAP] LOAD_FAILED` logging.

### Follow-up — /version came back `"commit": null` in production; RAILWAY_GIT_COMMIT_SHA doesn't apply to this project's deploy method

User actually hit the new endpoint against
`crave-production.up.railway.app` and got back `{"commit": null, ...}`
— both of the previous fix's sources came up empty. Root cause, worth
recording since it wasn't obvious going in: `RAILWAY_GIT_COMMIT_SHA` is
only populated for a GitHub-connected deploy, where Railway itself
clones the repo. This project deploys via `railway up`, which uploads
the local working directory as a build artifact instead — no git clone
happens on Railway's side at all, so that env var was never going to be
set, and the git-fallback (`git rev-parse HEAD` run inside the
container) came up empty too, meaning Railpack's build doesn't carry
`.git` into the image either. Confirmed the deploy log the user pasted
separately: `railway.toml`/`railway.json`'s `startCommand` already runs
`alembic upgrade head` automatically on every deploy, so that part
requires no separate manual step (a correction to earlier advice in
this same thread to run it separately via `railway run`).

Since neither mechanism this project actually uses could ever populate
`commit`, switched the primary source to a file stamped fresh right
before each deploy: `backend/GIT_COMMIT.txt` (gitignored — regenerated
every time, never committed), read via
`Path(__file__).resolve().parents[4] / "GIT_COMMIT.txt"`. Added
`deploy.sh` at the repo root specifically so this isn't one more manual
step to forget (the exact failure mode that caused the original "still
broken" report) — it stamps the file from `git rev-parse HEAD`, warns
if there are uncommitted changes (since the file would then reflect
HEAD, not the actual working tree being uploaded), runs `railway up`,
and prints the exact `curl` command plus expected commit to verify
against afterward. `RAILWAY_GIT_COMMIT_SHA` and the git-fallback stay in
the code as secondary sources in case the deploy method ever changes to
a GitHub-connected one.

`tests/test_debug_routes.py` (+2, net +1 after removing the now-
inapplicable env-var-only test): the stamped file wins even when
`RAILWAY_GIT_COMMIT_SHA` also resolves (proves priority order), and the
env var is still used as a fallback when no file exists.

Verified: backend suite passes (606 — 605 previous, net +1), stable
across two runs. No frontend changes in this follow-up.

**Next step for the user**: run `./deploy.sh` from the repo root instead
of `railway up` directly, then `curl
https://crave-production.up.railway.app/api/v1/debug/version` — its
`commit` should now match `git rev-parse HEAD`. Once that's confirmed,
re-test the map and paste whatever `[MAP] FEATURES_LOADED` or `[MAP]
LOAD_FAILED` line appears.

### Follow-up — ran deploy.sh, /version STILL came back null: had gitignored the exact file the fix depends on

User ran the new `deploy.sh`, deploy succeeded (health check passed),
but `curl .../debug/version` still returned `"commit": null`. Checked
Railway's own CLI docs before guessing again this time: `railway up`
respects `.gitignore` by default when deciding what to include in the
upload — and the previous follow-up's own `.gitignore` edit had added
`backend/GIT_COMMIT.txt` to it (reasoning at the time: "it's generated,
never meant to be committed"). That reasoning solved the wrong problem
— it kept the file out of git history, but it also meant `railway up`
silently excluded the file from the *upload*, so the container never
had it, and `/version` had nothing to read. A self-inflicted repeat of
the exact class of mistake this whole sub-thread has been about:
asserting a fix works without checking the specific mechanism.

Fixed by removing it from `.gitignore` (documented in a comment there
now, explaining why it's deliberately absent) and having `deploy.sh`
delete the file itself right after `railway up` returns (via `trap ...
EXIT`, so it's cleaned up even if the deploy fails partway through) —
this keeps it out of git history without ever putting it in
`.gitignore`, so `railway up`'s upload can't exclude it, and it never
lingers as an untracked file between deploys either.

No app code changed — `.gitignore` and `deploy.sh` only, no new backend
tests needed. Full backend suite still passes (606), re-run for
stability after this change with no code touched.

**Still open**: waiting on the user to re-run `./deploy.sh` and re-curl
`/api/v1/debug/version` to confirm `commit` is finally non-null and
matches `git rev-parse HEAD`, then re-test the map.
