# Crave — End-to-End Audit & Error Log

Audited: full repo (frontend, backend, root/deployment config), static read-only review (no build/runtime available). Ordered by severity within each section.

---

## CRITICAL — Breaks requests or features right now

1. **Menu API response schema mismatch → guaranteed 500.**
   `backend/app/services/menu/materialize_menu_truth.py` (`_serialize_menu`) writes each item with key `confidence_score`. `backend/app/api/schemas/menu.py`'s `MenuItemOut` requires a field called `confidence` (no default, required). FastAPI response validation fails on every successfully-materialized menu. This is why menus never render even when scraping worked.
   **Fix:** rename the field on one side to match the other.

2. **Duplicate route registered at the same path — one handler is dead code, unreachable landmine.**
   Both `backend/app/api/v1/routes/places.py::get_place_menu` and `backend/app/api/routes/menus.py::get_place_menu` are wired to `GET /api/v1/places/{place_id}/menu`. `places.py`'s version wins (registered first in `app/api/v1/routes/__init__.py`) and returns `{"items": [...]}`; the `menus.py` handler (the one with the `confidence`/`confidence_score` bug above) never actually runs today. The frontend (`frontend/src/api/menu.ts`) happens to match the winning shape — but only by coincidence. Reordering router includes, or removing the inline route in `places.py`, silently swaps in the broken handler.
   **Fix:** delete one of the two handlers; keep one canonical menu route.

3. **`menu_snapshots` table has no Alembic migration.** The SQLAlchemy model (`backend/app/db/models/menu_snapshot.py`) exists, but grepping all of `backend/alembic/versions/*.py` finds zero references to the table. Every write from `MenuSnapshotWriter` fails against a missing table — caught by a broad `except`, logged, never surfaced.
   **Fix:** generate and apply the missing migration.

4. **Auth flow (Google/Apple sign-in) cannot complete on a real device.** `frontend/src/components/AuthSheet.tsx` calls `supabase.auth.signInWithOAuth({ provider })` with no `redirectTo`, no `expo-auth-session` usage (it's installed in `package.json` but never imported anywhere), no `WebBrowser.openAuthSessionAsync`, and no `Linking` listener. `frontend/app.json` has no `scheme` field, so there's no deep link for Supabase to redirect back into the app. The backend/session logic (`authStore.ts`) is legitimate — it's just unreachable. **Sign-in does not work on device.**
   **Fix:** add a URL scheme to `app.json`, wire `expo-auth-session`/`WebBrowser` + a `Linking` redirect handler.

---

## HIGH — Silently drops or serves wrong data

5. **The real scoring engine is orphaned; a placeholder formula is what actually runs.** `backend/app/workers/recompute_scores_worker.py` implements the intended production scorer (signal decay, `compute_place_score_v4`, cache invalidation) — but it is never imported or called anywhere. The scheduler (`app/scheduler.py`, every 15 min) and the CLI job (`app/jobs/recompute_scores.py`) both call `recompute.py`'s `_compute_master_score`, a "Phase 1" placeholder (`confidence + operational_confidence + local_validation - hype_penalty`, flat `+0.15` if `has_menu`) that never reads menu confidence, signal decay, or per-signal data at all. Five other scoring modules (`place_score_v2/v3/v4.py`, `master_score.py`, `confidence_aggregator.py`, etc.) are dead relative to what's scheduled. Ranking quality is silently capped at the crude formula, and feed/response caches never get invalidated on recompute (only the orphaned worker did that).
   **Fix:** point the scheduler/job at the real v4 scorer, or formally retire the unused modules.

6. **Map: category filter is silently ignored.** `frontend/src/api/map.ts` sends `category` as a query param; the backend route (`backend/app/api/v1/routes/map.py`) only reads `category_id`. FastAPI drops unknown params — filtering by category on the map does nothing, no error.

7. **Search: `limit` param is silently ignored.** `frontend/src/api/search.ts` sends `limit`; `backend/app/api/v1/routes/search.py` only accepts `page`/`page_size` (default 20). Any attempt to constrain result count is a no-op.

8. **Map: category is never returned by the backend and never read correctly by the frontend — bottom-sheet field is permanently blank.** `MapBottomSheet.tsx` renders `feature.category`, but the backend's `GeoJSONProperties` schema has no `category` field, and `map.tsx`'s `selectedFeature` builder only copies `{id, name, tier, image}` anyway. Every pin's detail sheet shows no category, always.

9. **Map: no viewport/bounding-box refetching on pan or zoom.** `map.tsx` only refetches on city change or GPS location change (fixed `useEffect` deps). There's no `onRegionChangeComplete` handler. Combined with a hardcoded `DEFAULT_RADIUS_KM = 5.0` (never zoom-aware, never sent by the frontend), anything outside the initial 5km fixed box never appears no matter how the user pans/zooms the map. This is the single biggest reason the map "feels broken" — real map apps always requery on region change.

10. **No marker clustering.** Up to 1,000 places can be returned in one call (`MAX_LIMIT=1000` in `map.py`) and are rendered as individual `<Marker>`s with no clustering library. Dense areas will show unreadable overlapping pins.

11. **Menu pipeline: the capable extractor never runs.** A thin extractor (single fetch, no PDF/JS support) is the only one wired into the scheduled `menu_worker.py`. A much more capable extractor (`menu_extraction_router.py` — PDFs, JS-rendered pages, GraphQL, browser escalation) exists only as manual debug scripts, never scheduled or reachable from any route. Most real restaurant menu pages need the capable one.

12. **Menu worker eligibility filter drops valid places.** `menu_worker.py` only processes places where `Place.website IS NOT NULL`. Places whose menu source lives elsewhere (Grubhub URL, discovery candidates) without `website` set are never processed.

13. **Frontend errors are swallowed, not surfaced.** `frontend/src/components/ErrorState.tsx` is defined but never imported/rendered anywhere. `hitlistStore.ts` collapses all failures into two hardcoded strings; `useTrending.ts` catches and discards errors entirely (`.catch(() => {})`). A real backend 500 is invisible to both user and developer.

---

## MEDIUM — Wiring/architecture problems and tech debt

14. **`app/core/errors.py` is a completely empty file**, unreferenced anywhere — the codebase's structure implies a centralized error handler was intended but never built.

15. **Hardcoded default secret with no production guard.** `Settings.secret_key` defaults to `"change-me-in-production"` with no validator forcing an override when `app_env == "prod"`. A deploy that forgets to set `SECRET_KEY` boots silently with a public default.

16. **Confusing route-file organization.** `backend/app/api/routes/menus.py` sits outside the `v1` package but is imported cross-package directly into the v1 router (`app/api/v1/routes/__init__.py`). It looks like a parallel non-versioned API surface but isn't — it's a one-off import breaking the versioning convention.

17. **Auth applied inconsistently.** `require_api_key` guards `POST/DELETE /api/v1/hitlist/*` but not `GET /api/v1/hitlist/{user_id}`. Also, `require_api_key` allows all requests through when `API_KEY` is unset — a silent bypass, not a hard failure, if the env var is ever missing. Moot today since both `.env` files have the key set — but also moot because **the entire `/api/v1/hitlist/*` surface is dead**: the frontend calls `/api/v1/saves` (`saves.ts`/`hitlistStore.ts`) instead, not `/hitlist`.

18. **Pervasive silent-failure pattern.** Broad `except Exception` blocks that log and continue (no re-raise) recur across `app/pipeline/` (`snapshot_writer.py`, `candidate_builder.py`, `candidate_cluster_builder.py`, `promotion_engine.py`, `website_discovery_runner.py`, `website_schema_runner.py`, `aoi_scan_job_runner.py`) and scheduler jobs — the same pattern that let the `menu_snapshots` migration gap go unnoticed. Any future schema/data-shape mismatch in these stages will fail the same invisible way.

19. **Alembic migration history shows an unrebased branch point** (`b7e2f3a1c9d0` with two divergent children later reconciled by an explicit merge migration). Currently fine, but signals migrations were generated on parallel branches without rebasing — one bad future merge away from a broken graph.

20. **`has_menu` is hardcoded `False`** in the map GeoJSON builder (`map_query.py`) and unused by any map UI — dead/misleading field on both ends.

21. **Duplicate/redundant tier label in `MapBottomSheet.tsx`** — a `TierBadge` chip says "CRAVE PICK," and a second `<Text>` directly below repeats the same tier name again in different styling.

22. **`FilterSheet.tsx`'s `GENERIC_FILTER_CATS`** lumps meaningful attributes (gluten free, halal, black-owned, romantic) in with truly generic ones ("other," "restaurant") and strips all of them from cuisine filter chips — the filter UI looks sparser than the data actually supports.

---

## LOW — Missing polish vs. standard apps (Yelp/DoorDash/Google Maps-style baselines)

23. **`PlaceCardCompact.tsx`** (search/saves results) has no image fallback — a place with no photo shows a permanent blurry placeholder blob, while the home feed's `PlaceCard.tsx` correctly falls back to an initial-letter tile.
24. **Dead placeholder buttons** in `app/(tabs)/more.tsx` — "Rate CRAVE" and "How CRAVE Works" are fully styled/tappable but wired to empty handlers.
25. **Inconsistent loading polish** — the feed's `SkeletonCard.tsx` animates (shimmer); the detail screen's `DetailSkeleton` is a static gray box.
26. **Design tokens applied ad hoc** — several components hardcode pixel/color values that happen to match the shared design tokens (`colors.ts`, spacing, radius) instead of importing them (`CitySelectorStrip.tsx`, `TrendingStrip.tsx`, `search.tsx`, `Toast.tsx`). Harmless today, but future token changes won't propagate to these spots.
27. **No pull-to-refresh or pagination outside the home feed** — `search.tsx` fetches a flat 30-item limit with no "load more"; `hitlist.tsx` has no `RefreshControl` at all.
28. **No 404/not-found route** — `app/_layout.tsx` registers only `(tabs)` and `place/[id]`; a bad/stale deep link falls through to Expo Router's default error screen instead of a friendly empty state.
29. **`EXPO_PUBLIC_API_URL` defaults to `http://localhost:8000`** in `frontend/src/api/client.ts` if the env var is ever missing at build time — `.env` is currently set correctly to the Railway production URL, but there's no safeguard/warning if that ever regresses.
30. **Map fallback region inconsistency** — `map.tsx`'s hardcoded `DEFAULT_REGION` fallback is Berkeley/Emeryville coordinates, while `cityStore.ts` defaults city selection to San Francisco. If both geolocation and city fetch fail, the map centers somewhere inconsistent with the rest of the app's assumed default city.

---

## Deployment & Repo Hygiene

31. **No deployment/CI config anywhere in the repo** — no Dockerfile, docker-compose, railway.json/toml, Procfile, vercel.json, or GitHub Actions workflow, despite `.env` pointing at a live Railway production URL. Deployment is apparently entirely manual via Railway's dashboard with nothing versioned.
32. **`expo-location` version mismatch** — pinned at `^55.1.8` while every other Expo module in `frontend/package.json` sits in the SDK-54-aligned range (`~15.0.x`). Likely fails `expo install --check` or breaks at build/runtime.
33. **`backend/requirements.txt` has only lower-bound pins, no ceilings**, and some minimums look ahead of any real release (`starlette>=1.0.0` — Starlette has never shipped a 1.0). A fresh `pip install` at deploy time risks resolving to broken/incompatible versions.
34. **`frontend/app.json` still has placeholder bundle identifiers** (`com.anonymous.crave`) and no `eas.json` — not configured for a real store build/submission.
35. **`backend/app/data/cache/js_bundles/` (49,427 files) is not excluded by any `.gitignore`** — a real risk of massive repo bloat if it's ever committed.
36. **`backend/.env` contains live secrets** (Supabase service role key, Google Places API key, API key, Grubhub session cookies). Root `.gitignore` does list `.env`, so it's nominally excluded going forward — worth confirming it was never committed historically.
37. A **git worktree** (`.worktrees/frontend-productization/`) sits at the repo root, duplicating frontend files on disk — easy to forget about and edit the wrong copy.
38. No root-level workspace tooling (no shared `package.json`/turborepo/nx) — frontend and backend are two fully independent projects with zero shared tooling. Not wrong, but means nothing enforces they stay in sync.

---

## Suggested fix order

1. Menu `confidence`/`confidence_score` field mismatch (#1) — one-line fix, unblocks menus immediately.
2. Delete the dead duplicate menu route (#2) and add the missing `menu_snapshots` migration (#3).
3. Wire the real scoring engine (#5) — biggest silent-quality issue in the whole app.
4. Fix map viewport refetching + radius (#9) and clustering (#10) — biggest "feels broken" issue.
5. Fix the two silently-dropped query params (#6, #7).
6. Fix OAuth redirect wiring (#4) — sign-in is currently non-functional on device.
7. Everything else in HIGH/MEDIUM, then LOW polish items, then repo hygiene/deployment config.
