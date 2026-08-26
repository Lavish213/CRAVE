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

### Follow-up — the map/geojson fix finally confirmed working, and the real root cause turned out to be different from the working theory

`/version` came back non-null and matching `HEAD` this time, confirming
the deploy mechanism itself was finally trustworthy. The map/geojson
timing re-test still showed ~58s though — expected, since the deploy
just confirmed didn't yet include the scheduler-worker split (Railway
config-as-code only). That split was completed this pass: a second
Railway service was created from the same repo running
`cd backend && python -m app.scheduler_worker` (its Start Command field
had to be set directly rather than via `railway.scheduler-worker.toml`,
since Railway's Config-as-Code feature was found to be deprecated —
existing files keep working until 2026-12-01, but a brand-new service
can't opt in after 2026-08-28), then `RUN_EMBEDDED_SCHEDULER=false` set
on the web service. Confirmed live: the worker service's own logs show
`scheduler_worker_started jobs=9`, and the web service's logs show
`scheduler_embedded_disabled` with no `apscheduler` activity at all.

**But the map endpoint was still ~60-67s after the split — proving the
embedded scheduler was never the actual cause of this specific latency**,
despite being a real, separate problem (correctly fixed anyway, and
worth keeping fixed for its own sake — request handling and background
jobs no longer compete for the same process). Root-caused for real this
time via three new diagnostic endpoints (`/api/v1/debug/map-query-plan`,
`/api/v1/debug/map-query-timing`, `/api/v1/debug/categories-query-plan`,
all gated behind `require_api_key`), verified live against production
step by step instead of guessing:

1. `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` on the base bounding-box
   query: 4.45ms, clean index usage on `ix_places_places_rank_score`.
   Ruled out the base query and the "missing spatial index" theories
   entirely (this app doesn't use PostGIS — plain float columns + a
   regular B-tree index, which is sufficient at this table size).
2. Per-phase timing of `fetch_places_for_map`'s three steps: base query
   0.61s, **`get_categories_for_places_bulk` 62.27s**, images bulk
   lookup 0.18s. Isolated the culprit to one specific function.
3. `EXPLAIN ANALYZE` on that exact categories-join query: 2.7ms, clean
   index usage (`place_categories` has both a composite PK and a
   dedicated `place_id` index; only 34,926 rows total — not remotely
   bloated). This proved the SQL itself wasn't the problem, pointing at
   ORM-level behavior instead of the database.
4. Read `Category.places`'s relationship config directly:
   `lazy="selectin"` (eager) — and `grep -rn "\.places\b"` across the
   entire `app/` tree confirmed **nothing anywhere ever reads
   `category.places`**. Every call to `get_categories_for_places_bulk()`
   (used by the map endpoint, and transitively by search/feed) was
   silently triggering SQLAlchemy to fully hydrate every returned
   category's *entire* list of places (each Place carrying its own
   eager relationships) — for a relationship no code path ever touches.
   `EXPLAIN ANALYZE` couldn't see this because it only tests the literal
   SQL text, not what the ORM does with the result rows afterward.

Fixed: `Category.places` changed from `lazy="selectin"` to `lazy="select"`
(true lazy, SQLAlchemy's own default) in `app/db/models/category.py`.
Added `tests/test_place_category_query.py`, including a regression test
that counts real SQL statements via a SQLAlchemy engine event listener —
a timing or functional assertion alone wouldn't catch a reintroduced
eager load on a small test dataset. Verified by temporarily reverting
the fix locally: the test correctly failed (7 statements instead of 1),
then passed again once the fix was restored.

`Place.categories`/`city`/`claims`/`truths`/`images` are also configured
`lazy="selectin"` — the same pattern, just not yet confirmed to be
costing anything in practice the way `Category.places` was. Deliberately
**not** touched in this pass: unlike `Category.places`, those
relationships may genuinely be relied on by serialization code
elsewhere, and changing them blindly risks a real regression rather than
removing dead weight. Worth a dedicated, careful audit later — check
each one's actual callers the same way this fix did, one at a time.

Live-verified end to end after deploying the fix (commit
`1a563262e8e3ebadf6299587ef9570b84decdc83`): cold cache with real
categories/images populated dropped from **~60-67s to 1.45s**; warm
cache to **0.007s**. Reviewed via the `code-review` skill (high effort)
before merging — no genuine defects found; confirmed independently that
the full suite (627 tests) passes stably and that the regression test
is real, not decorative.

Also fixed along the way, unrelated but discovered mid-investigation:
`main` on GitHub was missing 3 migrations (`user_blocks`,
`menu_submissions`, `user_streaks`) that were already live in
production — applied via `railway up` from this feature branch over the
course of many earlier sessions, but never merged to `main`. Since the
web service's Railway source is `main` with auto-deploy-on-push enabled,
any future GitHub-triggered redeploy would have failed identically to
how a freshly-created second Railway service failed the moment it tried
`alembic upgrade head` against `main`'s stale migration history. Merged
via PR #43 (resolving real conflicts with an already-merged R2
durable-photo-refresh PR along the way, keeping this branch's more
complete `r2_client.py`/`stale_image_refresher.py` versions), then PR
#45 for the fix described above. `main` now matches what's actually
deployed.

Verified: 627 backend tests passing (623 previous + 4 new), stable
across two runs. `npx tsc --noEmit -p .` clean (no frontend changes this
pass beyond what PR #43 already carried).

**Nothing still open from this specific investigation** — root-caused,
fixed, live-verified, reviewed, and merged to `main`.

### Follow-up — asked to keep going: researched DB pool sizing, audited every other eager-loading relationship in the app, fixed 3 small frontend items, then a broader bug-hunting sweep

Web-researched Railway Postgres's actual connection limits before
touching anything: default `max_connections = 100`. The engine's
pool config (`pool_size=20, max_overflow=40` — 60 max connections per
process, hardcoded in `app/db/session.py`) was sized for a single
process; now that the scheduler is a separate Railway service, two
processes each maintaining their own pool against the same database
could combine to 120 connections — already over that limit on its own,
before counting Alembic, the Console, or Postgres's own reserved
connections. Made configurable via `settings.db_pool_size`/
`db_max_overflow` (env vars `DB_POOL_SIZE`/`DB_MAX_OVERFLOW`), defaulted
conservatively to 10/10 (20 max per process, 40 combined) so each
Railway service can be tuned independently without a code change. Added
`test_db_session_pool_config.py`.

Then audited every other `lazy="selectin"` relationship in the app the
same way `Category.places` was audited in the previous entry — found 13
more (across `place.py`, `city.py`, `menu_item.py`, `menu_snapshot.py`,
`place_claim.py`, `place_feed_snapshot.py`, `place_image_fetch_log.py`,
`place_image.py`), confirmed via grep across the entire backend
(including Pydantic schema field names, to catch implicit access through
`from_attributes` serialization) that only `Place.categories` is ever
actually read anywhere — the other 13 were pure eager-load waste, same
bug class, same fix (`lazy="select"`).

One of these turned out to be a second live, previously-undetected
instance of the map bug's exact mechanism: `PlaceImage.place` being eager
meant `GET /api/v1/place/{place_id}` (one of the most frequently-hit
endpoints in the app) — which fetches gallery images via
`get_public_gallery()`, itself a full-`PlaceImage`-entity query — silently
reloaded each image's *entire* parent `Place` object graph on every
request, which then cascaded into Place's own (equally dead) eager
relationships. Found by writing a regression test for a smaller,
already-suspected fix (`place_detail_router.py`'s own `select(Place)` →
specific columns, mirroring `map_query.py`'s established pattern) and
watching the statement count come back as 9 instead of the expected ~3 —
traced the extra queries' stack trace directly to SQLAlchemy's
`_load_via_child`, which pointed straight at `PlaceImage.place`. Added
`test_place_detail_no_eager_load.py` (same statement-counting technique
as `test_place_category_query.py`).

Also fixed the 3 remaining "Low Impact" items from an earlier audit pass
that had never actually been done (confirmed via direct code checks, not
assumed from an old note):
- Distance-formatting logic was duplicated identically in `PlaceCard.tsx`
  and `PlaceCardCompact.tsx` — extracted to `scoring.ts`'s new
  `formatDistance()`, tested.
- `MenuSubmissionSheet`'s invalid-price error now renders inline next to
  the specific item that failed, instead of a generic banner with no
  indication of which item was wrong. The "add at least one item" error
  (not tied to any item) stays as the global banner.
- `rank/[placeId].tsx`'s "See my list" button now uses `router.push`
  instead of `router.replace`, so back navigation after ranking a place
  isn't lost.

Verified: 631 backend tests passing (627 + 4 new), frontend `tsc --noEmit`
clean, full jest suite 94/94 (90 + 4 new `formatDistance` tests), stable
across repeated runs.

Launched a broader bug-hunting sweep (N+1 query patterns, frontend
stale-response races in screens not yet audited, cache-key correctness
in other cached endpoints, missing `db.rollback()` after failed
statements sharing a session).

**The sweep caught a real gap in this session's own earlier work**: the
whole-app grep used to confirm `Place.city`/`.claims`/`.images` were
"never read anywhere" searched for literal `.attr` dot-access, which
missed the same data read via `getattr(place, "attr", default)` — the
exact "invisible to naive grep" trap already worried about for Pydantic
schema fields, just a different shape. Three real, confirmed usages:

- `app/workers/recompute_scores_worker.py::_score_batch()` reads
  `getattr(place, "city", None)` for city-aware scoring weights, looping
  over up to 500 places every 15 minutes
  (`app/scheduler.py::_job_score_recompute`).
- `app/services/images/image_ingest_service.py` reads
  `getattr(place, "images", ...)`, and
  `app/services/images/provider_image_extractor.py` reads
  `getattr(place, "claims", None)` — both looped over up to 100 places
  every ~5 minutes via `ImageWorker._select_places()`.

Rather than reverting the model-level `lazy="select"` default (correctly
removed everywhere it's genuinely unused, including the live, frequently-
hit map and place-detail endpoints), added explicit
`.options(selectinload(...))` at the three specific batch-fetch queries
that actually need it — the same pattern
`app/services/scoring/recompute_scores.py` already established for
`Place.categories`. Along the way, found `recompute_scores_worker.py`'s
own `_iter_place_batches()` is legacy/unused (per its own docstring —
`app/scheduler.py`'s real job builds its own query directly); fixed the
real, live site in `scheduler.py` and left a harmless option on the
legacy path too, in case it's ever revived.

Added two regression tests using real statement counting (a functional
assertion alone wouldn't distinguish "batched" from "one query per
place" — both return correct data): `test_recompute_scores_worker_
city_lookup.py` (5 places across 5 *distinct* cities, so the per-session
identity map can't accidentally dedupe repeated lookups of the *same*
city — confirmed reverting the fix costs 5 more statements, 12 vs 7) and
`test_image_worker_eager_load.py` (checks SQLAlchemy's own inspection
API directly rather than running the full ingestion pipeline, which
makes real outbound HTTP calls — confirmed by temporarily reverting the
fix and watching it fail).

Also found and fixed 3 more frontend stale-response races, same bug
class already fixed in `place/[id].tsx`, `craves.tsx`/`cravesStore.ts`,
`useTrending.ts`, and `rank/[placeId].tsx`:
- `app/user/[id].tsx` — tapping from one user's profile into another's
  could show stale data if the old request outraced the new one.
- `app/taste-profile/[userId].tsx` — same shape.
- `app/(tabs)/profile.tsx` — signing out and into a different account
  while a previous load was in flight could populate the new account's
  profile screen with the previous account's data.

No further findings survived verification for the other two bug
classes hunted (cache-key correctness in other cached endpoints;
missing `db.rollback()` elsewhere) — also applied one small consistency
fix along the way: `map_query_plan`'s own `EXPLAIN` failure branch was
missing the same `db.rollback()` its sibling `categories_query_plan`
already has (harmless in practice, since nothing else used `db`
afterward in that request, but fixed for consistency).

Verified: 633 backend tests passing (631 + 2 new), frontend `tsc
--noEmit` clean, full jest suite 94/94, stable across repeated runs.

### Follow-up — this repo's own CI caught a real, standing production bug none of this session's own testing could

Opened PR #46 with everything above. Subscribed to its activity, and its
"Backend (same suite, against real Postgres)" CI job — a second run of
the exact same suite, but against a real Postgres instance instead of
SQLite — failed with `psycopg2.errors.InvalidColumnReference: for
SELECT DISTINCT, ORDER BY expressions must appear in select list`, in
`search_query.py::search_places()`, not in anything touched this
session. `search_places()` builds `select(Place).distinct()`, then
(when the caller supplies `lat`/`lng`) orders by a computed distance
expression that was never part of the SELECT list — SQLite doesn't
enforce this rule at all, so it silently "worked" in every local test
run and never surfaced until run against real Postgres, which is also
what production actually runs. Same bug class already hit twice this
session while building the map-latency debug endpoints, just this time
in live search code.

**Practical impact**: any real search request that included `lat`/`lng`
— i.e. CRAVE's own location-aware "nearby search" feature, the exact
fix this proximity-ordering code exists for — would 500 against
production Postgres, every time, for as long as this code has existed.

Fixed with `add_columns()` to add the distance expression to the select
list explicitly, without disturbing `.scalars()`'s entity extraction.
Set up a real local Postgres 16 instance (available in this sandbox)
and ran the full suite directly against it, matching the exact
environment that caught the bug — confirmed all 5
`test_search_query.py` tests (which already existed, asserting real
sort-order correctness, not just "doesn't crash") fail before the fix
and pass after, on a fresh database each time (a first pass at this
reused the same Postgres database across runs and got misleading
results from leftover state — recreated it fresh per run to match how
CI actually behaves).

Also fixed two of this session's own new debug-route tests that
assumed the suite always runs on SQLite — they failed for a different
reason (a bad assumption, not a bug) once actually run against
Postgres. Made them conditional on the real configured database, and
added the missing positive-path coverage for the Postgres branch that
had previously only been verified manually via curl against production.

Verified: 633 backend tests passing (2 conditionally skipped depending
on which DB is active), stable across two runs each against both a
fresh local Postgres 16 instance and SQLite.

### Follow-up — root requirements.txt drift (pyarrow), caught by CI on PR #46

A second CI job on the same PR — "Backend (syntax + import check)" —
failed independently on the fix commit above, for a completely
unrelated, pre-existing reason: this repo intentionally keeps root
`requirements.txt` (Railway's actual build entry point — see the long
comment at the top of that file explaining why `-r backend/requirements.txt`
indirection breaks Railpack's build-context copying) as a byte-for-byte
duplicate of `backend/requirements.txt`, and CI has a dedicated step that
fails the build the moment the two drift apart. They had already drifted:
`backend/requirements.txt` gained `pyarrow>=18.0.0` at some earlier point
(for Overture Maps discovery ingestion — reads public Parquet directly off
S3), but the copy in the root file was never updated to match.

Confirmed via:
```
diff <(grep -v "^#" requirements.txt | grep -v "^$" | sort) \
     <(grep -v "^#" backend/requirements.txt | grep -v "^$" | sort)
```
which showed exactly one line of drift (`pyarrow>=18.0.0` present only in
`backend/requirements.txt`). Nothing else in either file had diverged.

**Practical impact**: root `requirements.txt` is what Railway's zero-config
Python build actually installs from — if this had reached a real deploy,
pyarrow would be missing from the production install and every Overture
Maps discovery ingestion call would fail at import time.

Fixed by copying the `pyarrow>=18.0.0` line (with its full explanatory
comment) verbatim into root `requirements.txt`, matching the file's own
documented convention ("Edit backend/requirements.txt first, then copy its
package lines here verbatim"). Verified the sync-check diff is now empty,
and re-ran the full backend suite (633 passed, 2 skipped) against both
SQLite and a freshly-recreated local Postgres 16 instance — clean on both.

### Follow-up — offline outbox queue for saves, plus a bug-hunting sweep across the app (PR #47)

Added a persisted `pendingSyncActions` queue to `cravesStore.ts`: a
network-level failure on save/unsave now keeps the optimistic state and
queues the action instead of rolling it back, so a genuinely-offline user
doesn't silently lose their save. Queue is keyed by placeId, not an
array — an add queued offline followed by a remove for the same place
before the queue flushes cancels out to nothing (no network call ever
needed) rather than queuing contradictory ops. Flushes on the next
successful `loadSaves()` and on app foreground (`AppState`), both proving
connectivity is back. Deliberately no NetInfo/new native dependency —
reuses the existing network-error classification already in
`_classifyError`.

A dedicated bug-hunting review pass (background research agent, same
technique used earlier this session) found and fixed 5 confirmed bugs,
each with a regression test:
- `upload/confirm` had no ownership check (any authenticated user could
  confirm any `image_id` — they're public via `GET /place/{id}`'s
  gallery) and no status guard, so re-confirming an already-`ready` image
  forced it back through processing, where its own dedup check matched
  it against its own stored phash and marked it `failed` — permanently
  destroying an already-published photo. Fixed with an ownership check
  and a pending-only state guard.
- Menu submission approval committed `status=APPROVED` before applying
  it, with a bare `except` swallowing any failure — a transient error in
  `materialize_menu_truth` left the submission stuck `approved` with
  `published_items=0` and no way to retry. Status now only commits after
  apply actually succeeds.
- Follow route wrote a duplicate `ActivityEvent` on a retried follow,
  since `follow_user`'s idempotent "already following" return gave the
  caller no signal to skip the side effect.
- `rankings/compare`'s final round could 500 on a client retry (response
  lost after the server-side commit already succeeded), hitting the
  ranking's unique constraint as an uncaught `IntegrityError`. Now
  returns the already-created ranking instead.
- `useLocation` cached a permission denial as final for the whole app
  session, with no way to recover after the user granted access from OS
  Settings and returned to the app. Now re-checks on every foreground
  transition.

Also fixed a local-only dev issue found along the way: `test_crave.db`
(the local pytest sqlite fallback) was never reset between separate local
runs, silently accumulating rows and causing spurious
`test_image_worker_starvation.py` failures unrelated to any code change.
`conftest.py` now deletes it on each local run.

Verified: 641 backend tests passing (633 + 8 new), frontend `tsc --noEmit`
clean, full jest suite 107/107 (94 + 13 new). Merged as PR #47.

### Follow-up — built a short food-video feature end to end: upload, processing pipeline, offline record/sync, feed (PR #48)

User shared a standalone Node.js/Redis/BullMQ reference scaffold (record
→ upload → ffmpeg compress → food-score → approve → feed, with an
offline-first client) for a TikTok-style short food-video feature and
asked for it adapted to CRAVE's actual stack rather than run as a
parallel service. Ported the whole thing onto this app's real
Python/FastAPI/Postgres backend and Expo/React Native frontend, reusing
patterns already established this session rather than introducing new
infrastructure:

- New `place_videos`/`video_templates` tables (`aa1bb2cc3dd4` migration,
  verified upgrade/downgrade/re-upgrade against real Postgres).
  `video_templates` seeded with 3 starter templates (cheese pull, first
  cut, drizzle/pour) as data, not code.
- Upload flow (`app/services/video/video_upload_service.py`) mirrors
  `upload_service.py`'s request/confirm shape, reusing the exact
  ownership + pending-only-status guards fixed there in the PR #47
  follow-up above — this feature was built with that lesson already
  applied, not discovered again. Also adds a real max-upload-size
  enforcement via an R2 `HeadObject` call before confirming (a presigned
  PUT URL can't cap size itself) — something the photo upload flow still
  doesn't have.
- Processing pipeline (`app/services/video/video_processing_worker.py`:
  download → ffprobe duration gate → ffmpeg compress → food-score →
  thumbnail → approve/reject) runs as a scheduler job
  (`app/scheduler.py`'s `video_processing`, every 3 minutes), not a
  Redis/BullMQ queue and not a FastAPI `BackgroundTask` — matches every
  other worker in this app, and keeps real CPU work (transcoding, ML
  inference) off the process serving live requests, same reasoning as
  the scheduler-worker split earlier this session. Being DB-polling
  rather than queue-based also sidesteps a real bug the reference
  scaffold had: its orphan sweep aged out (and destructively deleted)
  any row still "processing," with no way to tell "client never
  uploaded" apart from "worker's been down a while." Here a stale
  `processing` row is just re-claimed and retried on the next pass — no
  sweep needed for that case at all; the sweep that does exist
  (`reject_abandoned_pending_uploads`) only ever touches `pending` rows
  nothing else in the system will ever revisit.
- Food classifier (`app/services/video/food_classifier.py`) calls a
  TFLite interpreter directly in-process — no subprocess bridge needed
  now that the backend is already Python, unlike the reference scaffold
  which had to shell out to a separate Python process from Node. Fails
  fast with a distinct `FoodClassifierUnavailableError` (→
  `status='failed'`, retried later) when the model/runtime isn't
  installed, kept separate from a genuine low-score `status='rejected'`.
  Deliberately does NOT bundle `tflite-runtime`/`tensorflow` as a hard
  dependency — this repo has already been burned once by a
  bad-for-Railway's-build ML dependency (pyarrow, see the follow-up a
  few sections up). `requirements.txt` gains only `numpy`.
- Frontend: `videoQueueStore.ts` mirrors `cravesStore`'s offline-outbox
  pattern from the PR #47 follow-up above (record locally first, sync
  when connectivity returns), account-scoped so a queued video only
  syncs under the account that recorded it. Record screen
  (`app/record-video/[placeId].tsx`, `expo-camera`) with data-driven shot
  templates and timed beat-cue prompts (no hardcoded template list on
  the client). Video gallery embedded in place detail
  (`PlaceVideoGallery.tsx`) with in-place playback (`expo-video`). Added
  `expo-camera`/`expo-file-system`/`expo-video`, pinned to this
  project's actual Expo SDK 54 versions from
  `node_modules/expo/bundledNativeModules.json` after a plain `npm
  install` first grabbed much newer, incompatible versions from a later
  SDK line — worth remembering for any future `npm install <expo
  package>` in this repo: always cross-check against that manifest
  first, don't trust npm's default "latest" resolution.

Verified: 671 backend tests passing (641 + 30 new) clean against both a
fresh SQLite and a freshly-created local Postgres 16 database, frontend
`tsc --noEmit` clean, 116/116 jest passing (107 + 9 new). Migration
verified upgrade/downgrade/re-upgrade against real Postgres. Every
pipeline stage (duration reject, food-classifier-unavailable vs.
low-score rejection, successful approve, stale-processing reclaim,
abandoned-pending sweep) has a regression test. Opened as PR #48.

**Still open — deliberately out of scope for this pass, same as the
reference scaffold's own stated scope:**

- **The food classifier model itself.** Nothing scores real content yet
  — `food_classifier.tflite` doesn't exist, and `tflite-runtime`/
  `tensorflow` aren't installed (see the constraints above on why
  they're not just added blind). Handed off as its own self-contained
  task (a separate chat is working this) rather than attempted in this
  session, which has no network access to clone/train against the
  reference model repo or to verify a real Railway build.
- **Native rebuild required, not just a JS/OTA update.** `expo-camera`,
  `expo-file-system`, and `expo-video` are brand-new native dependencies
  added this pass — recording and playback won't work on an existing
  installed build until `expo prebuild` runs (or a new EAS build ships).
- **Never verified live.** Camera permission flow, actual recording,
  template selection, beat-cue timing, upload progress, and playback are
  typecheck-clean and unit-tested at the store/API level only — nothing
  in this feature has run on a real device or simulator. This is a
  materially bigger unknown than the equivalent caveat on the saves
  outbox (PR #47), which is at least simple state-machine logic with no
  hardware in the loop; a camera/recording flow is exactly the kind of
  thing that looks right in code and breaks on first real touch
  (permission dialogs, camera lifecycle across app backgrounding,
  device-specific recording quirks).
- **Content moderation beyond automated food-score gating.** No
  report/flag path for a live video (the photo pipeline already has this
  — see `app/db/models/image_report.py`'s `ImageReport` model,
  `AUTO_HIDE_REPORT_COUNT = 3` distinct-reporter threshold, and
  `app/api/v1/routes/moderation.py`'s review-queue routes — a
  `VideoReport` model mirroring that exact shape, keyed on `video_id`
  instead of `image_id`, is the natural fit). No human review queue for
  borderline food-scores either — right now a video either clears
  `video_food_score_threshold` (0.5 default) and auto-approves, or
  doesn't and auto-rejects; there's no middle band that lands
  pending-review instead of being decided automatically. Needs: (1) a
  `VideoReport` table + `POST /videos/{id}/report` route + a
  `router_moderation`-style admin review router alongside the existing
  photo one, (2) a product decision on what score range counts as
  "borderline" (e.g. `threshold - 0.15` to `threshold + 0.15`?) and
  whether a borderline video defaults to hidden-pending-review or
  visible-pending-review while awaiting a human call.
- **The 30s–1min "auto-highlight" fallback.** Right now anything over
  `video_max_duration_ms` (10s default) is hard-rejected
  (`reject_reason='duration'`) — there's no path for a longer clip to
  get automatically trimmed down to a highlight instead of thrown away
  outright. Would need: new settings
  (`video_highlight_max_source_duration_ms` — the upper bound before
  even a highlight attempt gives up, and a target output window length,
  likely reusing `video_max_duration_ms`), and a new worker step
  inserted between the duration gate and compression in
  `video_processing_worker.py` — a sliding-window scorer that samples
  food-confidence across candidate windows of the source clip (same
  frame-sampling machinery `food_classifier.py` already has, just run
  per-window instead of once over the whole clip) and picks the
  highest-scoring window, then `ffmpeg`-trims to it before the existing
  compress step runs unchanged.
- **Push notifications on approved/rejected.** This isn't really a
  video-specific gap — CRAVE has zero push notification infrastructure
  of any kind (matches the "push notifications remain fully unbuilt"
  item logged much earlier in this document, still true). Building this
  for real needs, at minimum: the `expo-notifications` dependency (not
  installed), a device-push-token registration flow + a
  `device_push_tokens` table keyed by user_id, a backend service that
  calls Expo's push API, and then — only once that plumbing exists at
  all — two call sites to wire in: `video_processing_worker.py`'s
  approve and reject paths.
- **`video_food_score_threshold` (0.5) is an unmeasured placeholder** —
  needs tuning against real sample clips once the classifier is
  actually live and producing real scores, not guessed in advance of any
  real data.
- Everything else the reference scaffold itself called out as
  deliberately unbuilt (retry-limit/backoff *tuning* beyond the current
  flat `MAX_ATTEMPTS = 5` with no time-based backoff between attempts on
  either offline queue, multi-device concurrent-queue-draining — two
  devices racing the same account's outbox was explicitly scoped out of
  the original design, not just missed) still applies unchanged.

### Follow-up — video moderation, auto-highlight fallback, push notification plumbing, and real backoff (still PR #48)

Closes four of the "still open" items logged directly above: content
moderation beyond food-score gating, the 30s–1min auto-highlight
fallback, push notification plumbing, and time-based backoff on the two
offline queues. Everything here was buildable/testable without external
access (no device, no model file, no live Railway deploy needed) — the
food classifier model itself, native-rebuild verification, and live
on-device testing remain genuinely blocked on those and are unchanged
below.

- **Video moderation** (`app/db/models/video_report.py`,
  `app/api/v1/routes/moderation.py`). `VideoReport` mirrors `ImageReport`
  exactly — same reason vocabulary, same `UniqueConstraint(video_id,
  reporter_id)`, same `AUTO_HIDE_REPORT_COUNT = 3` threshold, deliberately
  duplicated rather than imported so video's moderation system stays
  independent of image's (same precedent `PlaceVideo` itself already set
  by not sharing a table with `PlaceImage`). The design question flagged
  when this was scoped — whether to reuse `PlaceVideo.status`/
  `reject_reason` for reports or add a genuinely separate field — was
  resolved by mirroring `PlaceImage`'s own precedent: `PlaceVideo` gained
  `moderation_status`/`moderation_reason`/`reviewed_at`/`reviewed_by`
  columns (migration `982f61551581`), kept fully separate from `status`
  (the processing-pipeline lifecycle). A video that clears the pipeline
  still starts `moderation_status='approved'` and can be pulled by either
  user reports or an admin decision without touching the field that
  records *why the pipeline itself* approved or rejected it. Routes:
  `POST /moderation/videos/{id}/report`, `GET /moderation/videos/queue`,
  `POST /moderation/videos/{id}/review` — same shape as the existing
  image routes, reusing `require_admin`. `GET /videos/feed` now filters
  on both `status='approved'` AND `moderation_status='approved'`.
- **30s–1min auto-highlight fallback**
  (`app/services/video/food_classifier.py`'s
  `find_best_highlight_window`, `app/services/video/ffmpeg_steps.py`'s
  `trim_video`, wired into `video_processing_worker.py`). New setting
  `video_highlight_max_source_duration_ms` (60s) replaces the old flat
  duration-reject ceiling for the upper bound; anything between
  `video_max_duration_ms` (10s) and the new ceiling gets a best-scoring
  window found via a sliding-window average over the same per-second
  frame scores `score_video()` already computes, then trimmed to that
  window with ffmpeg before compression runs as normal. Only a
  `REJECT_DURATION` now for a clip under the min or over the highlight
  ceiling. Not reachable from the current recording UI today — the record
  screen's own `MAX_DURATION_SEC` still caps at 10s — so this is
  forward-looking for whenever that cap loosens or a clip gets imported
  rather than recorded live.
- **Push notification plumbing** (`app/db/models/device_push_token.py`,
  `app/services/notifications/`, `POST`/`DELETE /account/push-token`).
  Backend infra only, exactly as scoped — there's no way to verify actual
  delivery to a device in this sandbox. `DevicePushToken` is keyed by the
  push token itself (not `user_id`), so a device logging out of one
  account and into another moves its existing registration instead of
  leaving a stale row still pointing notifications at the old account.
  `expo_push.py` is a thin, best-effort client for Expo's push HTTP API —
  chunks to its 100-message-per-request cap, and every failure mode is
  logged and swallowed, never raised, since a notification must never be
  able to affect the pipeline outcome it's reporting on.
  `video_processing_worker.py` fires one on every approve/reject (never
  on `failed`, which is a setup problem, not a verdict on the video).
  `expo-notifications` still isn't installed on the frontend and there's
  no token-registration UI flow yet — that half is unchanged from before.
- **Real exponential backoff** for both offline queues
  (`cravesStore.ts`'s `pendingSyncActions`, `videoQueueStore.ts`'s
  `videos`). Both gained a `lastAttemptAt` field; the retry delay (5s,
  10s, 20s... capped at 5 minutes) is computed from that, not from
  `queuedAt`/`createdAt` — the reference doc this session ported from had
  exactly that bug (a delay measured from queue time only ever grows, so
  an old-enough entry looks "due" on every check no matter how recently
  it just failed again). `flushPendingActions`/`runSyncPass` now skip
  (not abort the whole pass on) an entry still inside its backoff window,
  so a due entry queued behind a not-yet-due one still gets its turn.

Verified: 719 backend tests passing (698 + 21 new) clean against both a
fresh SQLite and a freshly-created local Postgres 16 database, migration
chain (`982f61551581`, `df7061f16615`) verified upgrade/downgrade/
re-upgrade against real Postgres, `requirements.txt` still in sync
(nothing new needed — `requests` was already a dependency). Frontend:
`npx tsc --noEmit` clean, 123/123 jest passing (107 + 16 new, split
across both stores' backoff coverage). Pushed to the same PR #48; PR
description updated to reflect all four additions.

**Still open, unchanged from the list above:**

- The food classifier model itself (`food_classifier.tflite` doesn't
  exist, `tflite-runtime`/`tensorflow` aren't installed) — still handed
  off as its own self-contained task, no network/training compute in this
  sandbox.
- Native rebuild required for `expo-camera`/`expo-file-system`/
  `expo-video` — still nothing has run on a real device or simulator.
- `expo-notifications` frontend dependency + device-token-registration UI
  flow (permission request, calling the new `POST /account/push-token`)
  — the backend half now exists, the frontend half doesn't yet.
- `video_food_score_threshold` (0.5) and the review-queue's implicit
  "borderline" band are still unmeasured placeholders — need tuning
  against real sample clips once the classifier is actually live.
- Multi-device concurrent-queue-draining (two devices racing the same
  account's outbox) — still explicitly out of scope, unchanged.

### Follow-up — wired up the real food classifier model + frontend push notification registration (still PR #48)

Closes two more items from the lists above: "the food classifier model
itself" and half of "push notifications" (the frontend registration
flow — the backend infra was already built). Both were previously
assumed blocked on network access this sandbox doesn't have; that
assumption turned out to be wrong for GitHub specifically (git clone,
raw.githubusercontent.com, and PyPI/npm all work through this session's
proxy, even though generic web browsing doesn't) — worth remembering for
next time something looks blocked on "no network access."

- **Food classifier model** — cloned Pramit726/MobileNetV2-FoodClassifier
  (MIT) directly rather than trusting its README, which doesn't actually
  mention the model file is committed straight into the repo (not a
  release/LFS asset). Verified by inspection, not assumption: input
  `(1,224,224,3)` float32 and output `(1,82)` softmax match
  `food_classifier.py`'s existing preprocessing exactly, and the 82 class
  names were recovered from the training notebooks (Keras's
  alphabetically-sorted `class_names` order) for `labels.txt`.
  - Found a real dependency landmine before it could hit Railway:
    `tflite-runtime` 2.14.0 (the only version on PyPI) is built against
    numpy 1.x and throws a `SystemError` importing under numpy 2.x, which
    this repo's own `numpy>=1.26.0` pin already permits. Switched to
    `ai-edge-litert` (Google's current package, tflite-runtime's
    successor, identical `Interpreter` API) instead, confirmed clean
    under numpy 2.x by actually reproducing the failure and the fix.
  - Ran the real model against real images (food photo crops from the
    model's own training-data preview notebook, a real dog photo,
    an abstract logo) rather than trusting the architecture on paper.
    Real food scored 0.988-1.000, real non-food scored 0.52-0.57 — a
    workable gap — but the abstract logo scored 0.972 for "Egg". That's
    not a tuning problem: softmax classifiers are well documented to be
    overconfident on inputs unlike anything in their training set, and no
    threshold fixes it. `video_food_score_threshold` moved from 0.5
    (a guess) to 0.8 (informed by the real gap found), documented
    honestly as a coarse filter in both `settings.py` and
    `food_classifier.py`'s module docstring — moderation/reporting (see
    the follow-up above) is the real backstop for whatever slips through.
  - New `test_food_classifier_real_model.py` runs the actual model
    against committed fixture images — the first test in this suite that
    isn't mocking the classifier away.
- **Push notification frontend registration** — `expo-notifications`
  (pinned to SDK54 via `bundledNativeModules.json`, same process as every
  other native dep added this session), a foreground notification
  handler (without one, notifications silently don't show while the app
  is open — an easy-to-miss expo-notifications default), and
  `usePushNotifications.ts`: requests permission, fetches the Expo push
  token, calls the `POST /account/push-token` route that already existed
  with nothing calling it.

Verified: 722 backend tests passing (719 + 3 new, including the
non-mocked real-model test) clean against both a fresh SQLite and a
freshly-created local Postgres 16 database, `requirements.txt` sync
verified with the new `ai-edge-litert` line. Frontend: `npx tsc --noEmit`
clean, 129/129 jest passing (123 + 6 new).

**Still open:**

- **A real Railway build has never confirmed `ai-edge-litert` installs
  cleanly there** — this repo's own established caution (pyarrow's
  history) applies to any new dependency until a real deploy proves it,
  and this sandbox has no Railway credentials to run one.
- **Native rebuild + live device testing** — unchanged from above. Adding
  `expo-notifications` is one more native module needing the same
  `expo prebuild`/EAS build the camera/video deps already needed.
- **`extra.eas.projectId` isn't set in app.json** — a fresh Expo project
  doesn't have one by default; needs `eas init` against a real EAS
  account (this sandbox has none). `usePushNotifications.ts` checks for
  it and no-ops with a clear dev-log message if it's missing, rather than
  crashing, so this doesn't block anything else — but push tokens
  genuinely won't register until it's set.
- **The threshold (0.8) and the model choice itself are still informed by
  a handful of manually-picked test images, not a real validation set or
  actual CRAVE video frames.** Revisit both once real user-submitted
  clips exist to test against.
- **The 82-class ingredient vocabulary is a domain mismatch with CRAVE's
  actual content** — trained on raw/whole ingredients (an apple, a raw
  chicken, a spice jar), not plated restaurant dishes (a burger, a bowl
  of ramen). It still separated real food from real non-food cleanly in
  testing, so it's a usable first pass, but a model actually trained on
  plated dishes (or one with an explicit "not food" class, which would
  let `_score_frame` do something more principled than max-softmax) would
  likely perform meaningfully better. Not attempted here — out of scope
  for "wire up what already exists," a genuinely new modeling task.

### Follow-up — full bug-hunting pass over the video system + EAS/Railway deploy debugging (still PR #48)

User ran the actual EAS build and Railway deploy from their own machine
in parallel with this work — surfaced its own real problems, all fixed:

- **`development-simulator` EAS build profile added** (`frontend/eas.json`)
  — the plain `development` profile targets a real device, which needs
  a paid Apple Developer Program account to provision. This variant
  builds for the iOS Simulator instead, skipping Apple Developer Portal
  auth entirely.
- **A local `git rebase` went wrong on the user's machine** and got
  committed with literal `<<<<<<</=======/>>>>>>>` conflict markers
  still in `frontend/package.json` — git doesn't validate JSON on `git
  add`, so this landed on the branch and broke `npm install`, the
  frontend CI check, and every EAS build attempt. Pulled the broken
  commit into this sandbox, resolved the conflict properly (kept both
  sides — `expo-camera`/`expo-file-system` and `expo-dev-client`),
  regenerated `package-lock.json` from scratch rather than hand-merging
  it, and re-verified typecheck + full jest suite before pushing the fix.
- Confirmed along the way that this project's Railway deploys
  (`railway up`, a local-directory upload, not a GitHub-connected clone)
  make `GET /debug/version`'s `commit` field **structurally always
  null** — not a bug, already documented elsewhere in this file, but
  worth restating since it was used (incorrectly) as a deploy-success
  check this round. Real verification needs a route-existence check
  instead (hit something added only in the new code and check the
  status code isn't 404), which is what caught that an early `railway
  up` had actually shipped code from `83dbf5c` — months before the
  entire video feature branch even started.

Separately, ran a full review pass (`/code-review --pr 48`, high effort)
over the entire branch diff looking for real correctness bugs. Two real
ones found and fixed, both regression-tested:

- **`video_processing_worker.py`: R2 cleanup ran before the DB commit**
  on both the approve and reject paths. A crash in that window (OOM,
  deploy, container restart) left the row stuck at `status='processing'`
  with `orig_key` already deleted from storage — the next
  stale-processing reclaim would re-download it, 404, and misreport an
  already-fully-determined outcome as `'failed'`. On the approve path
  this additionally orphaned the already-uploaded `processed_key`/
  `thumb_key` objects, unreachable by any future retry. Fixed by
  committing the status change first, cleaning up storage after —
  matches the ordering `upload_service.py`'s photo-confirm flow already
  uses for the same reason.
- **`image_worker.py`: a failed stale-refresh attempt (`StaleImageRefresher
  .refresh_primary` returning `False`) shared the same
  `image_fetch_attempts`/`image_blocked` counter as "no images found for
  this place at all."** Since `image_blocked` has no reset path anywhere
  in this codebase once set (confirmed by grep — it's written in exactly
  one place), 3 transient refresh failures (an API rate limit, an
  outage) on a place with a perfectly healthy gallery permanently
  stopped it from ever refreshing its stale primary image again, forever
  — while correctly leaving alone the counter's actual intended purpose
  (a place with genuinely no findable images, which still blocks after 3
  tries, verified by a new contrast test).
- **Considered and deliberately left unchanged**: `GET /debug/version`
  has no `require_api_key`, unlike every other route in that file. An
  existing test (`test_version_never_requires_an_api_key`) explicitly
  locks that in as intentional, and this very debugging round depended
  on it being curl-able without a key to verify the Railway deploy. The
  data exposed (commit hash, Railway environment/deployment id) isn't
  meaningfully sensitive — the commit is already public via the repo
  itself. Flagged by the review as an inconsistency with the rest of the
  file, but overriding a working, tested, actively-relied-upon pattern
  without a real justification would have been the wrong call.

Verified: 725 backend tests passing (722 + 3 new: 2 for the
video-worker commit-ordering fix, net +1 for the image_worker fix which
replaced one test with two), clean against both a fresh SQLite and a
freshly-created local Postgres 16 database. Frontend: `npx tsc --noEmit`
clean, 129/129 jest passing, `package-lock.json` regenerated from
scratch and verified installable. Pushed to the same PR #48.

## Live sign-in outage — two real, separate bugs found via actual device testing (2026-08-25)

Live testing on a rebuilt simulator binary surfaced the reason nobody
could sign in or create an account, even after the Supabase project was
confirmed unpaused. Two independent, unrelated bugs stacked:

- **Bug 1 — EAS cloud builds never had real Supabase/backend config.**
  `EXPO_PUBLIC_SUPABASE_URL`, `EXPO_PUBLIC_SUPABASE_ANON_KEY`,
  `EXPO_PUBLIC_API_URL`, and `EXPO_PUBLIC_API_KEY` only ever existed in
  a local, gitignored `frontend/.env`. EAS Build has no `.easignore` in
  this repo, so it falls back to `.gitignore` to decide what to upload
  to its cloud build servers — meaning `.env` was silently excluded
  from every cloud build's archive. `frontend/src/lib/supabase.ts`
  reads these via `process.env.EXPO_PUBLIC_*` with an unvalidated `?? ''`
  fallback, so every EAS-built app had `createClient('', '')` baked in:
  looked installed and functional, silently could never reach Supabase.
  `frontend/app.config.js`'s own comment already documented this exact
  pattern for `GOOGLE_MAPS_ANDROID_API_KEY` (must be set as an EAS
  secret/env var, not just local `.env`) — it just was never applied to
  the other four vars. Fixed by creating all four as EAS project
  environment variables (`eas env:create`, scoped to
  development/preview/production) and doing a fresh build. No code
  change — config only.

- **Bug 2 — backend JWT verification used the wrong algorithm family
  entirely, not just the wrong secret.** Even after fixing Bug 1,
  Supabase sign-in itself succeeded (confirmed via a real 200 in
  Supabase's own auth logs), but every backend call using that access
  token failed with "Invalid token" — reachable from the app as an
  unsubmittable profile-setup screen. Root cause: the Crave Supabase
  project has migrated to Supabase's newer asymmetric JWT signing
  (confirmed by fetching its `.well-known/jwks.json` — an ES256 EC
  public key, no HS256 secret). `app/core/user_auth.py` was still doing
  `jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256"])`
  — structurally unable to verify an ES256-signed token regardless of
  what value the secret held. There was never a correct value to put in
  Railway; this needed a real code change.

  Fixed: `get_current_user_id` now verifies against the project's public
  JWKS (`PyJWKClient`, cached per-process, algorithms `["ES256",
  "RS256"]` — deliberately excludes HS256, since a shared-secret
  algorithm has no business being verifiable from a public JWKS at all).
  `settings.supabase_jwt_secret` replaced with `settings.supabase_url`
  (same value as the frontend's `EXPO_PUBLIC_SUPABASE_URL`); the prod
  startup guard in `app/main.py` updated to match. Added
  `cryptography>=42.0.0` to both requirements files (required by PyJWT
  for ES256). **Railway's `SUPABASE_URL` env var must be set to
  `https://thzfsycylzjmofpzdopb.supabase.co` for this to work in prod —
  the old `SUPABASE_JWT_SECRET` var can be removed, it's unused now.**

  Also closed a real test-coverage gap found while fixing this: every
  existing route test bypassed `get_current_user_id` via
  `app.dependency_overrides`, so the actual signature-verification logic
  had zero direct tests — exactly the kind of gap that let an algorithm
  mismatch ship silently. Added `tests/test_user_auth.py`: generates a
  real EC keypair, signs tokens with it, and asserts against forged
  signatures, expired tokens, wrong audience, and the dev-bypass/prod
  guard paths — 10 new tests, all passing. Full suite: 735 passed, 2
  skipped, no regressions.

## Search screen tier badges — percentile-based tiering (2026-08-25)

Real complaint from live testing: nearly every Search result was tagged
"Hidden Gem" or "Worth Knowing," almost none "CRAVE Pick" or "Explore" —
the tier badges had stopped meaning anything.

Root cause, confirmed by reading `place_score_v4.py`'s actual weights
rather than guessing: the "structural" bucket (images, completeness,
menu, app links, recency) is hard-capped at 0.28, and any normally-
populated place — name, coordinates, a few photos, a website or menu —
hits close to that cap by default. The other buckets (authenticity from
blog/creator mentions, authority from awards) require real editorial/
social signal that most places in a cold-start catalog don't have yet, so
they sit near zero for the bulk of the catalog. Net effect: almost every
well-populated place clustered tightly around 0.28 — which straddles
exactly the "solid"/"gem" boundary in `scoring.ts`'s absolute-threshold
`getTier()` (0.22/0.32/0.42). The tiers were measuring data completeness,
not quality differentiation, and data completeness barely varies across a
Google-Places-sourced catalog.

Considered hand-tuning the absolute thresholds instead, but rejected it:
the app is pre-launch with almost no real hitlist/creator/blog signal
yet, so any thresholds calibrated against today's distribution would need
re-tuning again once real usage starts generating that signal and the
distribution shifts. Percentile-based tiering doesn't have that problem —
"top 5% of this city" stays true regardless of how the underlying score
curve moves over time.

Turned out cheaper than expected: `city_place_ranking_worker`
(`app/services/ranking/city_ranking_worker.py`) already computes and
stores each place's deterministic `rank_position` within its city, and
it's already scheduled hourly via `app/scheduler.py`'s `ranking_update`
job — that data was live and fresh, just never exposed past the backend.

Implemented:
- `app/services/query/rank_percentile_query.py` (new) — bulk-converts
  `rank_position` + a per-city count (via a single `COUNT() OVER
  (PARTITION BY city_id)` window-function query) into a `[0, 1]`
  percentile per place, keyed by place_id. A place with no ranking
  snapshot yet is simply absent from the result — callers must treat that
  as "unknown," not "worst."
- `rank_percentile` added to both `PlaceOut` (`/places`) and
  `PlaceCardOut` (`/search`) schemas, injected onto each ORM object
  before serialization (same pattern already used for
  `primary_image_url`) in both `routes/places.py` and `routes/search.py`.
- `scoring.ts`'s `getTier()` now takes an optional `rankPercentile` and
  uses percentile bands (0.95/0.80/0.40) when available, falling back to
  the old absolute-score bands only when a place has no ranking snapshot
  yet (e.g. added since the last hourly run). Same fallback logic mirrored
  in the backend's own `_rank_to_tier()` in `schemas/places.py` for
  consistency, though nothing currently reads that field client-side
  (confirmed by grep — `PlaceCard.tsx`/`PlaceCardCompact.tsx`/
  `TrendingStrip.tsx` always recompute tier from `rank_score` locally
  rather than trusting the API's `tier` field).
- Updated all three real call sites (`PlaceCard.tsx`,
  `PlaceCardCompact.tsx`, `TrendingStrip.tsx`) to pass
  `place.rank_percentile` through.

Verified: 7 new backend tests (`test_rank_percentile_query.py`) covering
percentile math directly — best/worst-in-city, even spread, sole-place-
in-city edge case, missing-snapshot handling, and per-city independence
(confirmed a place's percentile isn't polluted by a different city's pool
size). 7 new frontend tests in `scoring.test.ts` covering percentile
bands and the absolute-score fallback. Full suite: backend 742 passed (2
skipped), frontend 136 passed, `tsc --noEmit` clean.

## Photo/menu contribution permissions (2026-08-25)

Real product request: don't let every signed-in user directly publish
place photos or menu photos — restrict that to admin/staff/trusted
contributors (influencers, verified partners), with everyone else's
upload held for review and a notification if it's approved.

Turned out smaller than it first looked. `upload_moderation.py` already
had a genuinely sophisticated content pipeline (free local quality check
→ paid safety scan → GPS-verified/track-record trust logic →
auto-reject / hold-for-review / auto-publish), built to mirror how Google
Maps actually screens contributions. The actual gap was narrower: it
screened for *quality and safety*, not *who's uploading* — any signed-in
user's sharp, safe, non-flagged photo auto-published regardless of
identity.

- `app/core/contributor_access.py` (new) — `is_admin()` /
  `is_trusted_contributor()`, backed by the existing `ADMIN_USER_IDS` env
  var plus a new `TRUSTED_CONTRIBUTOR_USER_IDS` one. Same crude-allowlist
  pattern `moderation.py` already established for admin access — no role
  system exists in this app, and building one is a bigger change than
  either feature warrants. `moderation.py::require_admin` and
  `app/scheduler.py`'s moderation-queue health check now both delegate
  here instead of moderation.py's own now-removed private copy.
- `upload_moderation.py::screen_upload` — added the contributor-tier gate
  as the literal last step, after everything else: an upload that would
  otherwise auto-publish gets held (`MOD_PENDING_REVIEW`, reason
  `"untrusted_contributor"`) unless the uploader is trusted. A photo that
  actually fails quality or safety stays rejected regardless of who
  uploaded it — trust never rescues a bad photo, it only ever affects the
  would-have-been-approved branch. "Add menu photo" shares this exact
  pipeline (the menu-OCR pass only runs on an already-published image, so
  it's correctly blocked too) — one change covered both upload types.
- `moderation.py::review_image` — now sends a push notification on
  approve/reject, mirroring the existing video-review pattern
  (`_notify_video_outcome`) exactly.

Regression-tested two ways: `test_contributor_access.py` (new, 11 tests)
covers the allowlist logic directly, and `test_upload_moderation.py`
gained 3 new tests for the gate itself (untrusted → held, trusted →
publishes, rejected stays rejected regardless of trust). Also had to fix
8 *existing* tests across `test_upload_moderation.py` and
`test_image_processing_worker.py` that had encoded the old intended
behavior ("a plain user always auto-publishes") — correctly updated to
grant trust explicitly where that's not what the test is actually about
(quality/safety pipeline, primary-image election), rather than silently
broken by an intentional behavior change. Also caught and fixed a real
regression from the `_admin_ids` → `contributor_access.admin_ids` move:
`app/scheduler.py` imported the old private function directly and would
have hard-failed at import time.

Still open (tracked in `CRAVE_TOMORROW_PLAN.md`, not launch-blocking):
frontend button copy still reads "Add photo" for everyone rather than
"Suggest a photo" for non-privileged users (needs the frontend to know
the caller's tier — a small real follow-up, not done here), and there's
no "was this photo actually used as the place's photo" flag yet, just
notification-on-review-decision.

Verified: 756 backend tests passing (745 + 11 new/adjusted), 2 skipped,
no regressions.

## Place Detail screen audit (2026-08-25)

Per the doctrine's suggested screen-priority order (Search → Feed →
Place Detail → Filters → Craves → Map → You), audited `place/[id].tsx`
directly rather than starting on ML/personalization work — found two
real, previously-unnoticed bugs, both fixed same-session:

- **Upload confirmation lied about held photos.** `GET
  /upload/status/{image_id}` only ever returned the processing-pipeline
  `status` (pending/processing/ready/failed), never the separate
  `moderation_status`/`moderation_reason` fields added by tonight's
  contributor-tier gate (see above). A photo finishes processing
  (`status="ready"`) the moment it's uploaded, regardless of whether the
  moderation gate is holding it for review — so an untrusted
  contributor's photo would show `status: "ready"` and the app would
  tell them "Photo added" even though the photo was invisible, sitting
  in the review queue. Fixed by having the endpoint also return
  `moderation_status`/`moderation_reason`, and having
  `useImageStatusPoll` + `place/[id].tsx`'s confirmation toast branch on
  it: "Submitted for review" for `pending_review`, "wasn't approved" for
  `rejected`, "Photo added" only for `approved`. New dedicated test file
  `test_upload_status_route.py` (3 tests) — the route had zero prior
  coverage.
- **Two missed `getTier()` call sites from earlier tonight's
  percentile-tiering rollout.** `place/[id].tsx` and `(tabs)/index.tsx`'s
  `buildFeedRows` both called `getTier(place.rank_score)` without the
  `rank_percentile` argument that `PlaceCard.tsx`/`PlaceCardCompact.tsx`/
  `TrendingStrip.tsx` already had — meaning the place detail screen's own
  tier badge, and the Feed's "CRAVE Picks/Hidden Gems" section bucketing,
  were silently using the non-percentile fallback path all along. Fixed
  both call sites to pass `rank_percentile` through.

Verified: 759 backend tests passing (+3 new), 2 skipped; frontend
`tsc --noEmit` clean, 136 jest tests passing.

Feed pagination drift (background discovery inserting places every 5 min
shifts the offset-based window in `proximity_query.py`, causing repeats
across pages — client has a dedup guard as a stopgap) was evaluated for
a keyset/cursor rewrite and deliberately deferred: the sort key is a
computed `dist2` expression with no `id` tiebreaker, and there's no live
prod data available here to validate a rewrite against. Documented in
`CRAVE_TOMORROW_PLAN.md`, not started.

## Production incident: Railway crash-loop on stale `main` (2026-08-25)

Railway's `production` service (tracking the `main` branch) was crash-
looping on every boot: `alembic upgrade head` failed with `Can't locate
revision identified by 'df7061f16615'` and the healthcheck timed out.
Root cause: `main` was 30 commits behind this session's working branch —
stuck at PR #47 (`24b5001`) — missing the migration file for
`df7061f16615` (device push tokens), while the production Postgres
database's `alembic_version` was already stamped past that point (from
an earlier deploy that had tracked the newer code). Deploying the stale
`main` meant the running code's own migration scripts didn't include the
revision the database already expected.

Fix: fast-forwarded `main` to match the working branch (`main` was a
clean ancestor with zero divergent commits, so this was a pure
fast-forward, no conflicts) — first to `b97e283`, then to `3e97ebb`.
Diagnosed by: confirming the migration chain was self-consistent locally
(`alembic heads`/`alembic history`), confirming the production DB's
actual `alembic_version` via a Railway Console `psql` session, and
confirming `DATABASE_URL` matched between the Console and the web
service's own Variables tab (ruling out a wrong-database theory).

Took several redeploy cycles to actually resolve — Railway's "Redeploy"
button on an old failed deployment card re-runs *that exact pinned
commit*, not the branch's current tip, so repeatedly redeploying the
original failed card kept reproducing the same stale-code failure even
after `main` was fixed. A fresh deploy of the actual current branch tip
was needed to pick up the fix. Also ruled out (with hard evidence, not
just plausibility) a "Wait for CI blocking deploys" theory — checked via
the GitHub Actions API directly and confirmed both `ci.yml` and
`codeql.yml` completed successfully on `main` for the relevant commits.

Confirmed resolved: production's Active deployment is now built from
`3e97ebb`, migrations applied cleanly, healthcheck passing.

Process note for next time: keep `main` and the working branch from
drifting this far apart in the first place — this whole incident was
possible only because ~30 commits of real work sat on the feature branch
while Railway's production tracked a long-stale `main`.

## Recommendation Ledger, phase 1 (2026-08-25)

Per both doctrine docs' "instrument recommendations before building any
real ranking/personalization model" guidance — built now, while retrieval
(Search, Feed) is finally stable, rather than waiting.

Deliberately smaller than the doctrine's full spec: no algorithm
version, candidate set, component scores, penalties, or reason codes —
none of that exists yet, since there's no ranking model to log it for.
Captures exactly what's real today: which surface showed a place, at
what position/percentile, and what the user did about it.

- `RecommendationEvent` model + migration (`recommendation_events`
  table) — `app/db/models/recommendation_event.py`.
- `POST /api/v1/recommendations/events` — batch ingest, auth-optional
  (Feed/Search/Map are all browsable signed-out, so an anonymous
  impression is still real data). Each event in a batch is validated
  and clamped independently (`recommendation_event_service.py`) so one
  malformed entry never drops the rest of a batch — same one-bad-item-
  shouldn't-sink-everything principle as the per-item try/except pattern
  already used in `search.py`/`places.py`. Capped at 200 events/request.
- Also fixed the existing `GET /recommendations` route's identical
  silent-drop bug (`logger.debug` → `logger.exception` on serialize
  failures) while in that file — the same class of issue just fixed in
  `/search` and `/places` (see the rank_percentile clamp fix above).
- Frontend: `src/api/recommendationEvents.ts` +
  `src/utils/recommendationEventQueue.ts`, a small module-level batching
  queue (flushes every 4s or at 40 queued events). Fire-and-forget —
  this is telemetry, not user-critical state, so it deliberately does
  *not* get cravesStore's offline-outbox/retry treatment.
- Wired into Feed as the reference instrumentation: one impression event
  per place per newly-loaded page, one click event on place-card press.

Not done here (intentional fast-follows, not oversights): Search/Map/
Craves instrumentation using the same queue; save/rank event logging;
any actual analysis/dashboard reading this table back. The point of
this phase was making the data start accumulating now, not building the
consumer side before there's data to consume.

**Fast-follow instrumentation order (per follow-up review, supersedes
the "mechanically wire every screen" framing above): save → rank/
outcome → Search → Craves → Map, not screen-by-screen mechanically.**
Save and rank/outcome events are much higher-value learning signals
than more impressions — they're the actual "did the recommendation
work" data, not just "was it shown." After that:
- **Search** events should capture query + result position +
  reformulation (did the user immediately search again after this one —
  a strong implicit "that didn't work" signal), not just impression/click.
- **Craves** should capture import/save/resurface outcomes (a shared
  link that resolved to a match, a manually-saved place later opened
  again), not a generic impression per row.
- **Map** should only log meaningful marker exposure/selection (a pin
  actually tapped, or a cluster expanded), not every rendered pin —
  logging impressions for every pin on screen during a pan/zoom would
  be enormous volume for near-zero signal.

**Pre-deploy checks, addressed:**
1. Migration is purely additive (`create_table` + `create_index` only,
   no ALTER on any existing table) and cleanly rollback-safe
   (`downgrade()` is a plain `drop_table`).
2. Deploy ordering is safe by construction — `railway.toml`'s
   `startCommand` is `alembic upgrade head && uvicorn ...`; the app
   cannot start serving the new endpoint until the migration has
   already completed.
3. Added `recommendation_events_ingested submitted=/accepted=/rejected=`
   as an INFO-level log line in the route (was previously only
   returning the count to the caller, no server-side visibility) — the
   way to confirm post-deploy that the Ledger is actually receiving
   data, and rejected > 0 on a healthy client build would itself flag a
   real bug (typo'd surface/event_type, stale app version).
4. Impression semantics documented explicitly in
   `RecommendationEvent`'s own docstring: "impression" today means
   *load-based* ("this place's data arrived in a page response the
   client fetched"), not *viewability-based* ("the user actually saw
   this place on screen"). A place at the bottom of an unscrolled page
   still counts; a place stared at for ten seconds counts the same as
   one that flashed by mid-scroll. Deliberate simplification for this
   phase — revisit with `onViewableItemsChanged` + a time-on-screen
   threshold if/when viewability-weighted analysis actually matters.

Verified: 774 backend tests passing (760 + 14 new), 143 frontend tests
passing (139 + 4 new), `tsc --noEmit` clean.

Deployed and verified live: migration applied cleanly on Railway,
`recommendation_events_ingested` log line confirmed, and rows landed in
`recommendation_events` with correct `event_type`/`place_id`/`position`/
`rank_percentile`/`city_id`/`user_id`/`session_id` after a real Feed
scroll session.

## Feed's "Recommended for You" / "Trending" strips hidden for now (2026-08-25)

Live-tested against production data right after the Ledger deploy: both
chip strips look thin/unconvincing right now, and on inspection the data
backing them is exactly as weak as it looks — `get_recommendations`
falls back to generic catalog-wide top-rated places for any user with no
ranked places of their own yet (indistinguishable from "Trending" in
practice, despite the "for you" label), and `useTrending`'s save-based
signal is still thin enough to be closer to noise than real trending
behavior at this stage. Showing confident-looking suggestions backed by
weak data actively hurts trust more than showing none.

Decision: hide both strips behind a single `SHOW_FEED_DISCOVERY_STRIPS`
flag in `app/(tabs)/index.tsx` (currently `false`) rather than invest in
restyling them cosmetically first — the data problem is the real
problem, not the pill styling. Re-enable once there's real per-user
ranking history and enough save volume for these to reflect actual
behavior, not a handful of test taps. The underlying hooks
(`useRecommendations`, `useTrending`) and their backend routes are
untouched and still functional — this is purely a display-layer gate,
trivially reversible.

Verified: `tsc --noEmit` clean, 143 frontend tests still passing.

## menu_enrichment silently dead since ~11am: Chromium leak in the Playwright fallback (2026-08-25)

Diagnosed live via `/api/v1/debug/scheduler` and a direct `job_runs`
query: `menu_enrichment` (every 10 min) hadn't completed a single run
since 11:01am — every subsequent attempt showed `started_at` set,
`finished_at` null, no error, no success flag (process killed, not a
caught exception). One earlier run *did* succeed but took 2h04m.

Root cause: `browser_fallback.py`'s `extract_with_browser()` called
`browser.close()` only at the end of its happy path. A `page.goto()`
timeout — routine when scraping real restaurant websites — skipped it
entirely, leaking the headless Chromium process. Runs once per place in
a batch, so a normal per-site timeout rate accumulates leaked browsers
until the container OOMs mid-run, orphaning the job_runs row and
silently killing menu ingestion for good until the next deploy resets
the container.

Fixed: `browser.close()` now runs in a `finally` around the whole
navigation body. Also upgraded the failure log from `logger.debug`
(invisible at INFO level) to `logger.warning`. 4 new tests confirm
`browser.close()` is always called — success, `page.goto()` timeout,
mid-page exception, and even a `launch()` failure (nothing to close).

Verified: 778 backend tests passing (774 + 4 new).

Not yet re-verified post-deploy that `menu_enrichment` actually
completes cleanly now — next scheduled run after this deploys is the
real test; check `job_runs` again in ~15-20 min after deploy.

**Follow-up audit (same session):** grepped every `p.chromium.launch(`
call site in the backend — found the identical bug duplicated in 4 more
places (`browser_escalation.py`, `toast.py`, `extraction_controller.py`,
`toast_browser_scraper.py`'s two functions), all fixed the same way
(`try`/`finally`), 11 new tests. `browser_menu.py` already had the
correct pattern, confirmed clean. 789 backend tests passing.

## CI conflict-marker guard + public API rate-limit audit (2026-08-25)

Added a fast, independent CI job that greps the whole repo for
unresolved `<<<<<<<`/`=======`/`>>>>>>>` markers on every push/PR —
closes the class of "invalid source reached deploy" incident (compileall/
tsc already reject a marker sitting in real code, not one in a string,
comment, or non-code file).

Also did a fresh, from-scratch audit of every GET route's dependencies
(not assuming an earlier claimed count): every real user-facing endpoint
already had `rate_limit`. The actual gap was narrower — confined to
`debug.py`'s ops/diagnostic endpoints, 5 of 6 API-key-gated but
unrate-limited, `/version` with neither guard. Fixed by adding
`rate_limit` at the router level; `/health` stays correctly exempt.
New test asserts every debug route's dependant tree actually contains
`rate_limit`, not just present in the router's kwargs.

790 backend tests passing.

## Migration-validation CI job (2026-08-25)

Confirmed production is healthy on `aaf4845`: Railway deploy `2ca9a3a2`
started clean (migrations ran, `db=ok`, `/health` returned 200).

Added a new step to the existing `backend-postgres` CI job: after the
already-existing "upgrade head from empty" step, `alembic downgrade -1`
then `alembic upgrade head` against the same real Postgres container.
"From empty" proves the whole chain applies to a fresh DB but never
exercises any `downgrade()` and can't reproduce the actual production
upgrade path (already at the previous revision, now applying just the
new one). The round-trip does exactly that for the newest migration —
catches a broken/unimplemented `downgrade()` and an `upgrade()` that
isn't safe to re-run after it.

Verified locally against the real chain (local Postgres 16): full
upgrade from empty succeeds (5 most-recent revisions through
`f475d1becafc`), `downgrade -1` correctly reverses to `df7061f16615`,
`upgrade head` reapplies cleanly. Full backend suite: 790 passed, 2
skipped against both SQLite and a fresh-schema Postgres run (one earlier
full-suite Postgres run showed 3 failures — `test_hitlist_routes.py`,
`test_image_worker_starvation.py`, `test_menu_worker.py` — but a repeat
run against an identically-reset schema passed clean; non-deterministic,
not reproduced, not caused by this change — worth a closer look if it
recurs in real CI, but not chased further here).

## Recommendation Ledger: save/unsave + ranking outcomes (2026-08-25)

Reprioritized per explicit feedback: NOT cursor pagination yet (Feed's
ordering has computed distance, mixed ASC/DESC, and previously no
deterministic tiebreaker -- a keyset conversion is a retrieval
architecture change that needs its own evidence/design pass, not a
same-night "fully self-executable" task). Instead, extended the
Recommendation Ledger with the next-highest-value signal: confirmed
save/unsave and completed personal-ranking outcomes, not button taps.

**Save/unsave** (frontend, cravesStore.ts): a save or remove only logs
a Ledger event once the outcome is actually confirmed -- either
immediately (createSave/deleteSave resolves synchronously) or, for one
that failed with a network error and got queued in the offline outbox,
once a later `flushPendingActions` pass actually confirms it synced.
Tapping "save" while offline logs nothing yet; a non-network failure
that rolls the optimistic state back logs nothing either. `addSave`/
`removeSave` now take an optional `meta` (surface/position/
rank_percentile/city_id/query) so the event carries the same framing as
that screen's own impression/click events; `PendingSyncAction` carries
`meta` through so a flush confirming an action queued a while ago (or
across an app restart) still logs with the right context. Wired at
Feed's PlaceCard (surface='feed'), Place Detail (surface='place_detail'
-- new surface, plus new `unsave` event type, both one-line additions
to the backend model per its own "adding one is not a migration"
precedent), and the Craves tab's remove action (surface='craves').

**Ranking outcomes** (backend, rankings.py): logged server-side instead
of from the client -- `start_ranking`'s immediate-placement path and
`submit_comparison`'s converging-comparison path are the only two places
a ranking actually *completes*, and both already had an `already_existed`
replay guard for `record_ranked_place`'s activity-feed write; the new
`record_rank_outcome` call reuses that same guard, so a client retry
after a lost response can't double-log. Deliberately does NOT set
`rank_percentile` on these events -- that field means "this place's
city-percentile standing," a personal ranking's rank_score is a
different, unrelated signal, and conflating them would blur the exact
percentile-vs-personalization line called out as a guardrail earlier
this session.

New tests: 4 backend (unsave/place_detail acceptance, record_rank_outcome
persistence, route-level wiring on start_ranking) + 7 frontend
(cravesStore: confirmed-immediate logging, flush-confirmed logging,
NOT logging on offline-queue/rollback, default surface). Full suites
green: 794 backend (SQLite + fresh-schema Postgres, migration round-trip
re-verified), 150 frontend + clean tsc.

Deliberately not done yet, per explicit instruction: Search/Craves/Map
recommendation-event instrumentation (fast-follow, in that order, after
this).

## Ledger idempotency: one confirmed save/unsave -> at most one event (2026-08-25)

Follow-up on explicit feedback asking me to inspect whether multiple
confirmed sync pathways could ever double-log a save/unsave event.
Traced it through: addSave/removeSave's own immediate-success path and
the offline outbox's flush-confirmed path are mutually exclusive per
call (one logs immediately XOR queues, never both), and flushPendingActions
has a re-entrancy guard against concurrent overlapping passes -- so the
only real gap is a process kill in the narrow window between (a) a
successful sync + logged event and (b) that entry's removal from
pendingSyncActions actually persisting to AsyncStorage (zustand-persist
writes async, after the in-memory set() already returned). If the app
dies there, the next launch still sees the entry queued, retries the
(already-idempotent-server-side) save/unsave call, and would have
logged a second Ledger event for the same confirmed outcome.

Closed the gap with the same idempotency-key pattern this codebase
already uses for the identical class of problem (PlaceVideo.client_id,
see video_upload_service.py): a `client_event_id` generated once per
save/unsave attempt (reused across every retry of *that* attempt, never
regenerated), carried through PendingSyncAction so a later flush -- even
across an app restart -- logs with the same id. Backend: nullable
`client_event_id` column + NULL-safe partial unique index (migration
`d1f7127806d5`), `record_events` drops a within-batch duplicate and
anything already persisted before inserting, with an IntegrityError
fallback (insert one at a time) for a genuine concurrent-request race.
Every impression/click/rank event still has `client_event_id=None` and
is untouched by any of this (the partial index ignores NULLs).

New tests: 6 backend (pass-through/length-cap, within-batch dedup,
cross-request dedup at both the service and the real HTTP route layer,
NULLs never dedupe against each other) + 1 frontend (the actual
invariant: a failed retry then a successful sync reuses the exact same
client_event_id, asserted end to end through cravesStore). Full suites
green: 799 backend (SQLite + fresh-schema Postgres, migration
round-trip re-verified once more with the new column), 151 frontend,
clean tsc.

## Deploy/debugging doctrine: main was never updated + stale simulator JS (2026-08-25)

Two separate incidents while trying to production-verify the Ledger
work above, both worth codifying as standing rules so they don't cost
debugging time again:

**1. Backend commits pushed to the feature branch never reached
production**, because `main` itself hadn't moved — Railway's auto-deploy
and CI's `push` trigger both watch `main` specifically, and three
commits (`7495363`, `33a429e`, `20fa0b6`) landed only on
`claude/project-grade-systems-review-4ot7d0`. This wasn't a deploy
failure or CI lag; there was nothing to catch, because `main` genuinely
never advanced. Confirmed via `git merge-base --is-ancestor` (a clean
fast-forward, no divergence) and fixed with
`git push origin claude/project-grade-systems-review-4ot7d0:main`.
**Rule:** if a push to this session's working branch doesn't show up as
a new CI run on `main` within a couple minutes, check whether `main`
actually moved before assuming a deploy problem — `git log
origin/main..origin/<branch>` answers this in one command.

**2. `eas build:run` reruns a cached simulator binary, not current
code.** Confirmed the backend was correctly deployed and migrated
(`/api/v1/debug/version` + `alembic_version` both matched `20fa0b6`),
but a save/unsave test against a simulator produced zero
`recommendation_events` rows of *any* type, including impressions.
Root cause: `eas build:run` had relaunched a build from 2 hours prior
— an EAS-built binary bundles its JS at build time, so reusing a cached
artifact via `build:run` does not pick up anything committed since,
regardless of how current the backend is. **Rule: never infer frontend
code freshness from the backend's deployed SHA, and never assume
`eas build:run` is running current JS.** Before trusting any live
frontend test result, confirm the running client is actually consuming
current code — either a visible code-path tell (e.g. this session's
`SHOW_FEED_DISCOVERY_STRIPS = false` hiding Feed's discovery strips) or
by confirming the dev client is connected to a live Metro bundler
serving the current working tree, not a standalone/cached JS bundle.
A fresh `eas build --profile development-simulator` is the fallback
when a dev client won't reconnect to Metro.

## Recommendation Ledger production-certified; client-flush gap deferred (2026-08-25)

Added `GET /api/v1/debug/recommendation-events` (require_api_key +
rate_limit, same as this file's other ops endpoints) so the Ledger can
be checked over plain HTTPS instead of a Railway console session every
time.

Live production verification of the save/unsave pipeline, with direct
evidence rather than inference:
- Manually POSTing a real event with a fake place_id correctly rejected
  it (`accepted: 0`) via a foreign-key violation on `places.id` --
  surfaced a real, minor hardening gap worth fixing later:
  `record_events`'s IntegrityError fallback (built for a genuine
  client_event_id dedup race) silently swallows *any* IntegrityError
  the same way, including a bad foreign key, with no way to tell the
  two apart from the response. Not urgent -- real app traffic only ever
  sends real place_ids -- but worth distinguishing if this ever needs
  real debugging again.
- The same POST with a real place_id succeeded (`accepted: 1`), and the
  new debug endpoint immediately showed the persisted row with every
  field correct (event_type, client_event_id, place_id, surface).
  Confirms the whole ingestion -> validation -> dedup -> persistence
  chain is genuinely correct in production, not just in tests.

What's still open, deliberately deferred rather than chased further
tonight: confirming the *app itself* (not a manual POST) successfully
flushes `recommendationEventQueue`'s batched events end to end. Several
live save/unsave attempts through the actual dev-client build produced
zero rows despite clean client-side `addSave_ok`/`removeSave_ok` logs.
Given how much Metro reconnect/relaunch churn tonight's dev-client setup
required (`recommendationEventQueue`'s pending batch lives in a plain
module-level array with no persistence -- any JS module reload silently
wipes it before its 4s flush timer fires), this is far more likely a
dev-client-testing artifact than a real app bug, but it hasn't been
confirmed clean in a stable session. Re-check next time with a build
that isn't being actively reloaded (a real EAS build, or a dev-client
session left untouched for a few minutes after a save) before writing
this off entirely.

## Search-session instrumentation (2026-08-25)

Ledger fast-follow #2 (after save/unsave), per explicit spec: model a
search *session*, not per-keystroke noise, and keep search intent
separate from taste evidence until followed by a real action.

Backend: one additive column, `search_session_id` (migration
`f8a2c6d90e13`), narrower than the existing app-launch `session_id` --
groups one search interaction so a later analysis can reconstruct
query -> results shown -> selection -> reformulation. Reformulation is
deliberately *not* a logged event type -- it's derivable from
consecutive impression batches sharing a search_session_id with
different `query` values before any click, matching this codebase's
own "don't extend the schema preemptively" precedent. Reuses the
existing `impression`/`click` event types and `surface='search'`
exactly -- no new analytics system.

Frontend (`search.tsx`): a `searchSessionIdRef`, re-minted whenever a
fresh query starts from an empty box (not on every keystroke, not on
an idle timeout state machine). One impression batch logged the first
time a genuinely new debounced query's results arrive (capped at the
top 20 results, guarding against an unwieldy payload on a broad query),
deduped against re-renders of the same query via a ref. One click event
logged on result selection with its real position/query/session.
Trending (the pre-query zero state) is deliberately not instrumented
under surface='search' -- it isn't a search at all.

New tests: 1 backend (search_session_id pass-through/length-cap) + 2
frontend (impression batch capped/positioned/deduped-by-query; click
event carries the real position/query/session and doesn't fire from
trending). The frontend test is a full `SearchScreen` render via RTL +
react-query -- the first full-screen-component test in this repo
alongside `map.test.tsx`; needed `--forceExit`-equivalent awareness (a
benign "worker didn't exit gracefully" warning from a lingering
debounce timer, confirmed harmless -- the full suite still exits 0
without any special flags).

Full suites green: 803 backend (SQLite + fresh-schema Postgres,
migration round-trip re-verified), 153 frontend, clean tsc.

Deliberately not done yet, per the agreed sequencing: Craves/Map
instrumentation (queued after the design work), and no consumption of
these events into personalization -- that's Gate 2+ territory, once
real behavioral volume exists.

## 2026-08-26 — Place Detail: forensic inventory + first design-driven redesign

First screen rebuilt following the "inventory and grade before touching
code" process: full read of `place/[id].tsx` -> forensic inventory
(section -> keep/move/compress/remove -> reason -> backend field,
appended to `CRAVE_PLACE_DETAIL_SPEC.md` §8) -> implementation. No new
backend endpoint or schema change; frontend-only, using only fields
the existing `PlaceOut`/detail contracts already provide.

Changes: identity reordered (name leads, tier badge follows -- was
backwards); new decision strip (price / distance / directions)
directly under identity, with distance computed client-side via a new
`computeDistanceMiles` haversine helper in `scoring.ts` since
`GET /place/{id}` takes no lat/lng and `distance_miles` was always
null on this screen -- a real, previously-unnoticed gap, now closed
without a backend change; new "Why this fits" section synthesizing the
catalog percentile (labeled as a catalog fact, never "match %") and
real friend-ranking data, replacing the old standalone friend-rankings
section (moved, not duplicated); primary rank CTA moved to directly
follow it; Actions row's Directions button dropped as pure duplication
of the new strip; the flat emoji badge-chip row removed entirely (tier
already carried by the identity badge; delivery/menu chip duplicated
the Actions row's Order/Website buttons); menu section retitled "What
to get" and visually promoted to card-style rows; "Seen on social"
(craves) moved to progressive disclosure below the promoted menu
section, since it's lower-trust public UGC versus the friend-ranking
signal now surfaced in "Why this fits".

Explicitly NOT done, deferred as real backend gaps rather than faked:
open/closed status (`Place` has no `hours`/`is_open` field at all).

Preserved exactly, per the explicit constraint: all three
stale-response generation-ref guards (menu/craves/friend rankings) and
the upload `moderationStatus`-vs-`status` branching -- none of this
mechanics was touched, only the surrounding layout/copy.

Two judgment calls made during implementation, not fabrication risks
but genuine spec gaps worth naming: (1) the spec's example copy implied
a per-friend city-wide rank position ("Maya ranked it #4 in SF") that
no backend field actually carries -- written instead using only real
fields (friend count + top friend's real score/tier); (2) the spec
listed a "your own score" line inside "Why this fits" *and* kept the
Primary CTA's existing score display -- that would have been visible
duplication, so the own-score display stays in its one existing
correct place (the Primary CTA) rather than being shown twice.

`tsc --noEmit` clean; full Jest suite (153 tests, 13 suites) passes
unchanged -- no `place/[id]` test file exists yet, so nothing to update
and nothing regressed. No manual simulator verification yet (still no
automated visual-regression suite, per the frontend guide).

### Honest §33 re-score: 75/100 (was 57), target was 85+

Full category breakdown, against the actual rubric text (bible §33,
not from memory):

| Cat | Score | Why |
|---|---|---|
| A. Product purpose | 8/10 | Decision strip + "why this fits" now answer it directly; goes nearly empty for a cold-start place with no percentile/friends (falls back to a bare tier word) |
| B. Information hierarchy | 8/10 | Correct front-loading; removing the badge chip trades a fast glance for less clutter -- defensible, not proven |
| C. Decision usefulness | 11/15 | Real gain from distance+percentile+friends; capped by the still-missing hours data and the same cold-start thinness as A |
| D. Originality | 7/10 | "Why this fits" is genuinely CRAVE-specific, but this pass was IA-only -- no new visual language, still recognizably the old screen's skin |
| E. Personalization | 6/10 | Deliberately capped per doctrine, not inflated ahead of Gate 2 |
| F. Interaction design | 8/10 | Was 7 -- found and fixed a real defect while scoring: the new Directions chip was a bare TouchableOpacity/Text with no explicit touch-target sizing, unlike every other button on this screen |
| G. Performance | 8/10 | Unchanged, no regression |
| H. Error/edge states | 7/10 | Unchanged -- the explicit state-design list from the inventory (no-images placeholder, etc.) wasn't actually executed this pass, only the reorg was |
| I. Accessibility | 4/10 | Marginal gain (one new labeled control), no full pass done |
| J. Trust/explainability | 4/10 | Most-improved category -- "why this fits" is literally the explanation |
| K. Retention | 4/10 | Unchanged |

**Total: 75/100** -- "credible MVP" band. What's actually blocking
85+: D (needs a real visual-language pass, not just IA reorg -- this
was explicitly out of scope for this pass), C/A's cold-start thinness
(no fallback content when a place has neither a real percentile nor
any friend rankings -- "why this fits" currently just says the tier
word alone), and H (the inventory's full state-by-state design list
was written but not executed against actual JSX/styles). None of these
are fabrication risks -- they're real, honestly scoped remaining work,
not this pass's claim.

**Follow-up same day:** fixed the cold-start finding directly rather
than just logging it -- "Why this fits" now suppresses itself entirely
when there's no real percentile and no friend ranking, instead of
showing a bare tier word in a box. Small honest bump to A/C (roughly
76-77/100 now); does not change the two harder blockers (D's need for
an actual visual-language pass, H's unexecuted state-by-state design
list) -- still short of 85+.

**Decision:** rather than keep polishing this one screen against a
bigger scope than this round intended, move on to Feed per the
original sequence. Place Detail's remaining gap to 85+ (D: a real
visual-language pass, not just IA reorg; H: execute the full
state-by-state design list from the inventory -- no-images hero
placeholder polish, explicit partial-data confirmation, etc.) is
tracked here as a follow-up, not abandoned.

## 2026-08-26 — Feed: two real defects fixed, honestly scored (59 -> 65/100)

Read `app/(tabs)/index.tsx`, `PlaceCard.tsx`, `PlaceCardCompact.tsx` in
full and checked them against doctrine §22.1's own "Feed current
problems observed" list (already an inventory of sorts) before
touching anything. Unlike Place Detail, this was **not** a full
spec-driven IA rebuild -- the doctrine explicitly warns against two
things a full rebuild would tempt: reviving the hidden "Recommended for
You"/"Trending" strips (still correctly off, no real signal backs
them) and inventing the dynamic sections it lists as examples ("Best
for tonight," "Worth the drive," etc.) without real backend curation
logic behind them -- doing either would be exactly the fabrication
anti-pattern this whole design push exists to prevent. So this pass was
scoped to real, cheap, honest fixes only:

1. **Found a genuine duplication bug**: `getBadges()` re-emitted the
   tier as its own chip ("⭐ CRAVE Pick" / "💎 Hidden Gem") on top of
   the `<TierBadge>` already rendered elsewhere on the same card, on
   *both* `PlaceCard` and `PlaceCardCompact` -- confirmed by reading
   both, not assumed. Removed the tier branch from `getBadges()`
   entirely rather than patch each call site; the function's contract
   is now honestly "0-1 badge" (menu/delivery/off-grid are mutually
   exclusive), not "0-3."
2. **Added a real "why this matters" signal**: new `percentileCaption()`
   in `scoring.ts` -- "Top N%" shown as its own accented line on the
   card, but *only* for `crave_pick`/`gem` tiers with a real
   `rank_percentile`. Deliberately silent for `solid`/`new` tiers even
   though a percentile might exist -- "Top 55%" reads as an anti-signal,
   not a reason to care, so showing it would be technically true but
   actively counterproductive. This directly answers doctrine's
   "cards do not yet communicate why each place matters" finding,
   using a field the cards already had (`rank_percentile`) -- no new
   endpoint.

New/updated tests: `scoring.test.ts` -- badge tests updated for the
0-1 contract, 4 new tests for `percentileCaption` (both real tiers,
silent for solid/new even with a real percentile, silent with no
percentile even for a top tier). Full suite: 156 passed (was 153),
`tsc --noEmit` clean.

**Honest §33 re-score: 59 -> 65/100** ("functional but weak" both
before and after -- this pass did not clear a grade band). What's
actually blocking further movement, and why it's correctly out of
scope for a frontend-only pass: **A/C** need Feed restructured into
"small, high-confidence candidate sets" per doctrine's stated purpose,
which needs real backend curation logic, not a frontend reshuffle of
the same offset-paginated full catalog; **D** needs the same real
visual-language pass Place Detail is also waiting on. Both are real,
sized correctly as backend/design-system work, not something to fake
around in `index.tsx`.

## 2026-08-26 — Craves: Recommendation Ledger instrumentation, surface='craves'

Per explicit instruction: Craves and Map instrumentation done as two
separate passes, not one broad telemetry sweep -- this entry is Craves
only. **This is behavioral-measurement readiness, not a product/visual
change -- it does not move Craves' §33 score (still the 6/10 informal
rating in `CRAVE_STATE_OF_THE_APP.md`, unchanged).**

Instrumented the existing journey in `app/(tabs)/craves.tsx`, reusing
the existing Ledger path exactly (`surface='craves'`, same
`logRecommendationEvent(s)` utility every other surface uses):

- **Collection/list impression**: one bounded (`MAX_LOGGED_CRAVES_ITEMS
  = 20`), positioned batch logged for the primary Saves list every time
  `loadSaves()` resolves (initial load and pull-to-refresh) -- read
  straight from `useCravesStore.getState().saves` right after, since
  `loadSaves()` mutates the store rather than returning the fetched
  list.
- The "Craves" (matched social shares) and "Added" (manual place-name
  saves) sections get their own impression batches too, logged inside
  `loadCraves()`/`loadPlaceSaves()`'s own `.then()` handlers -- but
  **only for items with a real, resolved `place_id`**. An unmatched
  share/add has no place_id at all, isn't in the catalog yet, so it's
  excluded from the batch entirely rather than logged with a null id;
  its position in the batch is local to that filtered matched-only
  list, not its index in the raw (unfiltered, unmatched-items-included)
  array.
- **Selection**: a click event on any of the three sections' "open
  place" taps, with the real position matching its section's own
  impression batch (verified: the matched-only position, not the raw
  array index -- this was the one subtle bug risk worth a dedicated
  test for).
- **Save/unsave**: no new code -- `removeSave(placeId, userId, {surface:
  'craves', ...})` on this screen already went through cravesStore's
  certified idempotent path (client_event_id, partial unique index,
  same as every other surface) before this pass even started. Per
  instruction, did not add a second event system on top of it.
- **Filter/sort/section context**: Craves has no filter or sort
  controls at all (confirmed by reading the full screen -- no such UI
  exists), so none were instrumented; that would have been fabricated
  telemetry for controls that don't exist. The three sections
  (Saves/Craves/Added) *do* genuinely exist as distinct UI, so each
  gets its own impression batch -- section identity is reconstructed by
  which batch a place_id appeared in, not a new schema field, since the
  existing contract can already answer that question.
- **Retention framing, not new taste evidence**: this whole screen is a
  return to a place the user already chose once -- an impression/click
  here is re-engagement with existing memory, not fresh discovery
  signal the way a Feed/Search impression is. No new field encodes
  this; the `surface='craves'` tag itself is what lets any future
  consumption logic treat it differently from `surface='feed'` --
  documented explicitly in a code comment at the top of the
  instrumented section so this doesn't get silently reinterpreted
  later.

**Reconstruction verified**: Craves opened -> `loadSaves`/`loadCraves`/
`loadPlaceSaves` resolve -> one impression batch per non-empty section
(bounded, positioned, real place_ids only) -> a click event on any
section's open-place tap carries the same place_id/position as its
section's impression batch, so a click can always be matched back to
the specific impression it came from -> place/[id].tsx's arrival needs
no separate event (implied by the click) -> any save/unsave/rank
outcome that follows is already covered by the existing certified
paths (cravesStore's addSave/removeSave with `surface='craves'` set
here, and rankings.py's `record_rank_outcome`, un-surfaced but
user/place-keyed) -- no gap in the chain.

New dedicated test: `__tests__/craves.test.tsx` (3 tests) -- bounded/
positioned impression batch for the Saves list; click position matches
selection; matched-only filtering for the Craves section (the
unmatched-item-position bug this design was written specifically to
avoid). No backend changes, so no backend/migration gates run. Full
suite: 159 passed (was 156), `tsc --noEmit` clean.

## 2026-08-26 — Map: Recommendation Ledger instrumentation, surface='map'

Second half of the two-part instrumentation pass, deliberately separate
from Craves (own commit, own inventory). **Behavioral-measurement
readiness, not a product/visual change -- does not move Map's rubric
score.**

Inventoried the existing mechanics in `app/(tabs)/map.tsx` before
touching anything, since the instruction was explicit about not adding
events until this was understood: the region-fetch debounce
(`REGION_FETCH_DEBOUNCE_MS`), the coverage cache
(`lastFetchCoverageRef`/`isCoveredByPriorFetch` -- skips a fetch
entirely when a pan lands on already-covered ground), the stale-request
guard (`requestIdRef`), the spurious-first-region guard
(`hasHandledFirstRegionRef`, a documented iOS MapKit quirk), grid-based
clustering (`buildClusters`), and the bottom sheet's drag-to-dismiss
(`MapBottomSheet`). All of this was left completely untouched --
instrumentation only reads already-computed results, never changes
when a fetch fires.

- **Map-results impression**: one bounded (`MAX_LOGGED_MAP_FEATURES =
  30`), positioned batch logged only when a fetch actually *resolves*
  (inside `loadFeatures`'s and `loadSavedPlaces`'s existing success
  handlers) -- never on the debounce timer firing, and never on a pan
  that the coverage cache decides needs no new fetch at all. This is
  what makes it "after a settled/debounced region," not "on every pan":
  the existing guards already do that filtering; instrumentation just
  rides on their result.
- **No `rank_percentile`**: `NormalizedMapFeature` only carries an
  absolute `rank_score`, not the catalog percentile Feed/Search compute
  server-side. Left null rather than fabricated from some invented
  score->percentile conversion that doesn't exist server-side -- a real,
  minor gap, consistent with this session's rule against inventing
  signal.
- **No raw coordinate trail**: verified directly in the dedicated
  test -- a logged event never carries `lat`/`lng`/region data, only
  `place_id`, `position`, `city_id`, and the session id. What's shown is
  reconstructed from place_ids, not from where the map was pointed.
- **Pin/cluster selection vs. bottom-sheet selection vs. place-detail
  navigation** -- collapsed to **one** real Ledger click, deliberately:
  logged on the bottom-sheet's "open" tap (which already performs the
  navigation in the existing code), not on the bare pin tap that only
  reveals the preview sheet. In real usage a pin gets tapped, glanced
  at, and often dismissed without opening -- logging every glance as a
  full click would inflate the signal with "just looking" taps the same
  way logging every pan would have. This is a judgment call, documented
  directly in map.tsx's own comments, not a silent decision. Cluster
  taps get no event at all -- a cluster has no single place_id, it's a
  zoom gesture.
- **A stable map-session ID, with no new column**: reuses the existing
  `search_session_id` field rather than adding a second one -- its
  actual contract (nullable, opaque, client-generated, only meaningful
  within its own surface) was already exactly what Map needed; adding a
  new column would have been a schema change the instruction explicitly
  said to avoid unless reconstruction genuinely required it, and it
  didn't. Broadened the doctrine comment on both the backend model
  (`recommendation_event.py`) and the Pydantic schema to say so
  explicitly, since a column named `search_session_id` silently also
  meaning "map session id" would otherwise mislead the next person who
  reads it. Minted fresh on a deliberate restart of what's being
  explored (city change, or switching city<->saved mode) -- not on
  every incidental region change (GPS resolving shortly after mount
  doesn't count as a new session).
- **Position**: read from the last *logged* impression batch
  (`lastImpressionIdsRef`), not a fresh array lookup -- same pattern as
  Craves' matched-only position fix, so a click's position always ties
  back to a real, already-logged "this was shown" event.

**Reconstruction verified**: settled region/mode change -> fetch
resolves -> one bounded/positioned impression batch (place_ids + tier
context, no coordinates) -> bottom-sheet "open" tap logs one click with
the real position from that batch and the same session id -> detail
navigation is the same handler call, needs no separate event -> any
save/unsave/rank that follows from place/[id].tsx is already covered by
its own existing certified path.

Two test-infra changes, both backward-compatible: the shared
`__mocks__/react-native-maps.tsx` `Marker` mock now renders a real
pressable (was a no-op returning `null`) so a marker tap can actually be
simulated -- the pre-existing `map.test.tsx` never queried for these
elements and is unaffected (still 8/8 passing); and that same
pre-existing test file needed a new mock for
`recommendationEventQueue` since map.tsx now imports it (same poisonous
supabase-import-chain reason every other screen test already mocks this
one level down).

New dedicated test: `__tests__/map-instrumentation.test.tsx` (4 tests)
-- bounded/positioned impression batch with a stable session id and no
raw coordinates; click position matches the logged impression and
shares its session id, with a bare pin tap logging nothing; a cluster
tap logs nothing at all; a city change mints a fresh session id and
still logs saved-mode impressions. Full suite: 163 passed (was 159),
`tsc --noEmit` clean. Backend touched only two docstrings/comments (no
schema or logic change) -- ran the full backend suite anyway as a
sanity check: 803 passed, 2 skipped, unchanged from baseline. No
migration needed.

## 2026-08-26 — Debug endpoint gap found + fixed while preparing production verification

While preparing to verify actual deployed Craves/Map rows (surface
values, stable session id across impression -> selection, bounded/
positioned ids, no coordinates, no duplicate impressions, save/unsave
client_event_id preserved), found that `/api/v1/debug/recommendation-
events` didn't return `search_session_id` in its response at all --
the one field the "stable session id" check actually needs. The
verification would have been impossible to perform with the tool that
exists for exactly this purpose. Added it to the response. Full
backend suite re-run: 803 passed, 2 skipped, unchanged.

**Known technical debt, explicitly not fixed today**: reusing
`search_session_id` for Map (see the 2026-08-26 Map entry above) avoided
a real schema change, but the column's name is now actively misleading
-- it holds a Craves-adjacent... no, a Search- *and* Map-session id,
despite its name still saying only "search." The honest fix is a future
rename to a neutral `interaction_session_id` (a real migration: add
column, backfill/dual-write, drop the old one, update every read/write
site). Not doing that now -- a rename-only migration serves no
functional purpose today and this session's own standing rule is "don't
migrate for naming alone." Tracked here so it doesn't get forgotten,
not swept under the "it's just a comment" framing used when the reuse
was first made.

## 2026-08-26 — Place Detail: edge-state + accessibility pass (item 1 of the product-quality sequence)

Live verification of Craves/Map is paused on the user's side (simulator
friction) -- rather than block on that, moved to the next agreed item:
Place Detail's explicit edge-state/accessibility work, code-only, no
device needed for the work itself (screenshots for the eventual §33
re-score still will be).

- **No-photos state, honestly redesigned**: `ImageGallery` previously
  stretched the app's own icon full-bleed as a stand-in photo when a
  place had none -- reads as a broken/wrong image, not a designed empty
  state. Replaced with the same fallback language `PlaceCard` already
  uses elsewhere (muted panel + icon + text), so "no photo yet" finally
  looks like an intentional state instead of a rendering bug.
- **Real accessibility labels added to the photo gallery**: previously
  zero -- a screen reader had no way to know it was even looking at a
  photo carousel, let alone which photo or whether it was GPS-verified.
  Added `placeName`-aware labels ("Photo 2 of 4 for Nari, verified
  visit"), hid the raw verified-badge/dot-indicator text from the
  accessibility tree (`importantForAccessibility="no"`) since the photo
  label already covers it.
- **Decision-strip chips no longer read their raw emoji glyphs**: a
  screen reader previously read "💰 $$$" and "📍 1.8 mi" literally
  (VoiceOver reads emoji by name). Wrapped each in an accessible group
  with a clean label ("Price: $$$", "Distance: 1.8 mi"), hiding the
  visual text from the accessibility tree.
- **Section headings marked as headings**: name, "Why this fits"
  headline, "What to get", "Seen on social" now carry
  `accessibilityRole="header"` so VoiceOver/TalkBack's heading
  navigation (rotor) can jump between sections -- previously all
  identical plain text to a screen reader, no way to skim the page's
  structure non-visually.
- **Menu item rows grouped into one accessible element** each (name +
  description + price read as one coherent unit: "Margherita, wood-fired
  with basil, $16.00") instead of three separately-announced fragments.
- **Partial-data polish**: the identity meta line (category · address)
  now hides entirely when both are null, instead of rendering an empty
  string that still consumed a line of vertical space.
- **Real, confirmed, app-wide contrast gap found, not fixed here**:
  `Colors.textMuted` (`#555555`) on `Colors.background`/`Colors.surface`
  (`#0A0A0A`/`#1A1A1A`) computes to roughly 2:1 contrast -- well under
  WCAG AA's 4.5:1 for normal text. Used in many files across the app
  (menu category labels, avatar-fallback icons, etc.), so a real fix is
  a design-token change with app-wide blast radius, correctly out of
  scope for a single-screen pass. Did not introduce a new instance of it
  in today's own new code (`ImageGallery`'s no-photos label uses
  `textSecondary`, ~5.6:1, instead).

Not yet done from the full edge-state list: explicit designs for
partial API responses beyond the one case above, and the still-generic
`ErrorState`/offline distinction. tsc clean, 163 tests passing
(unchanged -- no test file exists yet for `place/[id].tsx` or
`ImageGallery` to update).

Next: the real visual-language pass (item 2), then re-score against
§33 with actual screenshots once the user is back on a simulator (item
3).

## 2026-08-26 — Place Detail: controlled visual-language pass (item 2)

Scoped explicitly as a Place Detail pass, not an app-wide design-system
rewrite. Design map (element -> problem -> treatment -> token/field)
was written and reviewed before any code changed; see the session
transcript for the full table. Summary of what actually shipped:

- **Identity**: name grows 24/800 -> 26/900, more top padding after the
  hero so the photo/video reads as the anchor with real whitespace
  before identity starts, not crowding directly against the last frame.
- **"Why this fits"**: the bordered/filled box is gone entirely --
  headline now carries the signal through typography alone (18px/800,
  colored with the place's own `tier.color`, already computed, no new
  field). This was one of several near-identical boxes stacked down the
  screen; removing it was the single highest-leverage de-chipping move.
- **Action row**: only **Save** keeps a bordered pill now (its saved/
  unsaved state is a real selection signal -- reserve blue for it, per
  direction). Website/Order/Add photo/Add menu photo/Report all became
  plain icon+label pairs, no border/background. Same handlers, same
  conditions, same accessibility labels -- pure visual de-emphasis.
- **Menu ("What to get")**: per-item bordered/filled boxes replaced with
  a hairline `borderBottomWidth` divider -- was the clearest instance of
  card-in-a-card repetition (up to 20 near-identical boxes in a row).
- **Local accessible secondary-text treatment**: new `QUIET_TEXT`
  constant in this file only (`= Colors.textSecondary`), replacing
  every `Colors.textMuted` use on this screen (menu category labels,
  two icon colors). Per instruction, did **not** touch the global
  `Colors.textMuted` token -- that needs an audit of every consumer
  first, logged separately (see the prior entry) as app-wide debt.
- **Decision strip, primary CTA**: left as-is -- already correctly
  minimal / already correctly the one prominent action.

New dedicated test file `__tests__/place-detail.test.tsx` (5 tests) --
none existed before. Covers: name renders with `accessibilityRole=
"header"`; "why this fits" suppressed with no percentile/friend signal;
the no-photos empty state's accessible label; a menu item's grouped
accessibility label; Save button reflects saved/unsaved state. Caught
and fixed one real bug in the test itself while writing it (not in
product code): a fresh `{user: {...}}` object literal returned from a
mocked `useAuthStore` on every render retriggered the friend-rankings
effect (keyed on `[id, user]`) infinitely -- fixed by giving the mock a
stable `user` reference, the same category of bug this session found
in real code before (unstable references defeating effect dependency
checks), just this time in test infrastructure instead of product code.

Full suite: 168 passed (was 163), `tsc --noEmit` clean. No backend
changes.

### Honest §33 re-score -- confirmed vs. provisional

Per instruction: visually-dependent categories are capped as
provisional until reviewed against actual simulator screenshots, not
counted as landed just because the code changed.

| Cat | Confirmed (code/test-verifiable) | Provisional (pending screenshots) | Why |
|---|---|---|---|
| A. Product purpose | 8/10 | -- | Unchanged, no functional change |
| B. Information hierarchy | 8/10 | 9/10 | Real change (bigger name, more whitespace, de-boxed why-fits) but hierarchy is fundamentally a *visual* claim -- not confirming the bump until it's actually seen |
| C. Decision usefulness | 11/15 | -- | Unchanged, no data change |
| D. Originality | 7/10 | 8/10 | The de-chipping is the most direct answer to "reorganized legacy UI vs. distinct CRAVE screen" -- but that's exactly the claim this pass must not grade itself on without a screenshot |
| E. Personalization | 6/10 | -- | Deliberately capped per doctrine, unchanged |
| F. Interaction design | 8/10 | -- | Real tradeoff, not a clear win: removing borders from 5 action buttons could reduce their tap-discoverability as much as it reduces clutter -- not claiming a win either direction without live confirmation |
| G. Performance | 8/10 | -- | Unchanged |
| H. Error/edge states | 7/10 | -- | Unchanged this pass (covered last pass) |
| I. Accessibility | 6/10 | -- | Up from 4 -- **not capped provisional**, because the mechanism (accessibilityRole/Label presence, contrast math) is objectively verifiable from code and tests, not a subjective visual read. Still not a full screen-reader pass on a real device. |
| J. Trust/explainability | 4/5 | -- | Same content, only presentation changed |
| K. Retention | 4/5 | -- | Unchanged |

**Confirmed-only total: 77/100.** **Provisional total if the visual
changes land as intended: 79/100.** Both still "credible MVP" band
(70-79) -- this pass moved the screen further in the right direction,
it did not cross into "competitive" (80+), and it certainly didn't
reach 85+. That's the honest number, not "85 because more code
changed." The actual test of whether this crossed from "reorganized
legacy UI" into "a distinct CRAVE decision screen" is a screenshot
review against real content (a `crave_pick` place, a cold-start place,
a no-photos place) once the user is back on a simulator -- not
something further code-reading can settle.

## 2026-08-26 — Four quick wins: FK-error logging, Feed category scoping, Place Detail offline message, Search/Map filter bars

Ranked list of easy-for-me, code-only items; user picked 1-4.

1. **Backend**: `record_events()`'s per-event IntegrityError fallback
   now logs a distinct warning for a genuinely bad `place_id`, separate
   from a legitimate `client_event_id` dedup race -- both previously
   raised the identical exception and looked indistinguishable from the
   caller's side (`{"accepted": 0}` either way), confirmed live during
   the Craves/Map production verification pass. Doesn't change what
   gets accepted, only what's visible in logs. New test; 804 backend
   tests passing (was 803).
2. **Feed**: category filter chips now derived from the currently-
   loaded `places`, not a global `fetchCategories()` call across the
   whole catalog -- picking a category with zero matches in the current
   city previously showed "Nothing here yet" with no explanation why.
3. **Place Detail**: distinguishes a network-level failure (no response
   at all) from a real server error, same signal cravesStore's
   `_classifyError` already uses -- both previously showed the
   identical "Couldn't load this place" message. 2 new tests.
4. **Search and Map**: both had zero filter UI at all (confirmed by
   direct audit). Both now reuse the existing `FilterSheet` component
   (price + category chips) rather than inventing a second filter
   paradigm:
   - Search: categories derived from current results (same fix as
     Feed's #2 above). Filtering narrows only what renders --
     impressions still log against the full, unfiltered results
     (matches Feed's existing precedent). A filtered-in result's click
     position is looked up in the original results array, not the
     filtered list's index, so a click always ties back to the
     position actually logged in its impression batch. New "no matches
     for these filters" empty state with a one-tap clear.
   - Map: filtering applied *before* clustering, so a filtered-out
     place never contributes to a cluster's count/center either.
     `NormalizedMapFeature` carries a single `category` string, not an
     array, so the match predicate differs slightly from Feed/Search's
     `.some(...)` -- a direct equality check instead. Filter button
     added inline with the city-selector strip (Map had no header row
     to reuse the way Feed/Search do). Same position-preservation fix
     for a filtered-in marker's click.

New tests for both filter additions, including the trickiest part
(click position surviving a filter) in each. Full suite: 172 passed
(was 168), `tsc --noEmit` clean.

## 2026-08-26 — Debug router: separate server-only DEBUG_API_KEY, closing the audit's #1 finding

An external forensic audit (run against `70ac944`, independently
reproducing the same lockfile/dependency-tree state and test counts as
this repo) flagged the same gap already noted in this session's own
rate-limit-hardening pass on `debug.py`: `API_KEY`/`x-api-key` is the
app-wide key the frontend sends on every request via
`EXPO_PUBLIC_API_KEY`, which Expo compiles into the shipped JS bundle --
not a real secret, only a "some copy of the app" signal. Gating
`recommendation-events` (raw per-user event rows), `scheduler` (job-run
internals), and the three `EXPLAIN ANALYZE` endpoints behind that same
key meant anyone who extracted it from the bundle had operator-equivalent
read access.

Fix: `app/core/auth.py` gained a second dependency, `require_debug_api_key`
(header `x-debug-api-key`, env var `DEBUG_API_KEY`) -- a server-only
secret set only in Railway, never referenced by any `EXPO_PUBLIC_*` var.
Unlike `require_api_key`'s dev-friendly bypass-when-unset, this fails
closed: an unset `DEBUG_API_KEY` rejects every gated route outright
(503), by design -- there's no open mode for raw production data dumps
and query-plan execution. All six non-`/version` routes in `debug.py` now
use it instead of `require_api_key`; `/version` remains intentionally
public (no sensitive data, just a commit/environment lookup).

Rewrote `tests/test_debug_routes.py` accordingly (the old tests unset
`API_KEY` to exercise the bypass path -- that path no longer exists for
this router, so every test that previously relied on it now sets
`DEBUG_API_KEY` and sends `x-debug-api-key` instead), plus new tests:
fails-closed-when-unset, and an explicit check that the old public
`x-api-key` no longer authenticates these routes at all. Documented the
two-key model in new `backend/docs/DEBUG_ENDPOINTS.md`.

Full backend suite: 806 passed (was 804), 2 skipped -- confirms nothing
else in the app depended on the old debug-route auth behavior.

**Still open, not done by this fix:** rotating the existing (already
chat-exposed) `API_KEY`/`EXPO_PUBLIC_API_KEY` value itself. That's
independent hygiene -- rotating it does not close this gap (a rotated
public key is still a public key), and this fix does not require it to
be effective. Flagged again because it still hasn't been done.
