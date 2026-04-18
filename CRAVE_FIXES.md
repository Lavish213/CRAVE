# CRAVE Fix Log

Last updated: 2026-04-16

---

## Backend Fixes

### Alembic migration `1c24b5d58ddf`
- **Bug:** `WHERE is_active = 1` in partial index — PostgreSQL rejects boolean = integer
- **Fix:** Changed to `WHERE is_active = true`

### SQLite → PostgreSQL data migration
- **Bug 1:** `place_images.url` column VARCHAR(512) too short — actual URLs up to 593 chars
- **Fix:** Widened to VARCHAR(1024) before import
- **Bug 2:** `place_claims.is_verified_source`, `discovery_candidates.resolved`, `discovery_candidates.blocked` passed as integers to boolean columns
- **Fix:** Added to BOOL_COLS mapping

---

## API Contract Fixes

### `frontend/src/api/search.ts`
- **Bug 1:** Sent `{ q }` — backend expects `{ query }` → 422 on every search
- **Bug 2:** Expected bare `PlaceOut[]` — backend returns `{ total, page, page_size, items }`
- **Bug 3:** Search items have `primary_image` field — normalization layer expected `primary_image_url`
- **Fix:** Changed param to `query`, unwrap `data.items`, wired `normalizePlaceOut` on all items

### `frontend/src/api/menu.ts`
- **Bug:** Backend returns `{ items: MenuItem[] }` — frontend called `.slice()` directly on the object → TypeError crash
- **Fix:** Unwrapped: `return Array.isArray(data?.items) ? data.items : []`
- **Note:** DB has 0 menu items — menu section is empty but no longer crashes

### `frontend/src/api/map.ts`
- **Bug 1:** `fetchMapGeoJSON({ city_id })` — backend requires `lat` + `lng` → 422, map error banner
- **Bug 2:** GeoJSON coordinate order is `[longitude, latitude]` — was used as `[lat, lng]` → markers placed in wrong location
- **Bug 3:** Raw GeoJSON passed to map component — no normalization
- **Fix:** Rewrote to send `{ city_id, lat, lng }`, call `normalizeMapFeatures(data)`, return `NormalizedMapFeature[]`

### `frontend/src/api/places.ts`
- **Bug 1:** `normalizePlaceOut` existed but was never called in `fetchPlaces`, `fetchTrending`, `fetchPlaceDetail`
- **Bug 2:** No canonical `image` field on `PlaceOut` — each UI component used a different field name
- **Fix:** Added `image: string | null` to `PlaceOut`, wired `normalizePlaceOut` in all three functions

---

## Normalization Layer

### `frontend/src/api/normalize.ts` (created)
- `normalizePlaceOut` — canonical `image` field with fallback chain:
  `primary_image_url || primary_image || images[0] || null`
- `NormalizedMapFeature` interface with `coordinate: { lat, lng }`
- `normalizeMapFeatures` — extracts `coords[1]` as lat, `coords[0]` as lng from GeoJSON geometry, filters invalid coords

---

## Store Fixes

### `frontend/src/stores/cityStore.ts`
- **Bug:** No `initCities()` — cities never auto-fetched on first install, `selectedCity` stayed null
- **Fix:** Added `initCities()`: fetches cities, sorts alphabetically, auto-selects San Francisco (fallback: first city) if `selectedCity` is null

### `frontend/app/_layout.tsx`
- **Bug:** Manual `fetchCities()` + `selectCity()` calls — bypassed normalization and auto-select logic
- **Fix:** Replaced with single `initCities()` call

---

## Feed Screen Fix

### `frontend/app/(tabs)/index.tsx`
- **Bug:** Feed empty on cold launch — `selectedCity` null at mount, `loadPage` returns early, feed never renders
- **Fix:** Added `initCities` to store subscriptions; `useEffect` calls `initCities()` when `selectedCity` is null before returning

---

## Image Rendering Fixes

### `frontend/src/components/PlaceCard.tsx`
- **Bug:** `source={place.primary_image_url ?? undefined}` — field frequently null
- **Fix:** `source={place.image ?? undefined}`

### `frontend/src/components/PlaceCardCompact.tsx`
- **Bug:** Same as PlaceCard
- **Fix:** `source={place.image ?? undefined}`

### `frontend/app/place/[id].tsx`
- **Bug:** `allImages = [place.primary_image_url, ...(place.images ?? [])]` — first element null when no `primary_image_url`; ImageGallery receives null in array
- **Fix:** `allImages = place.images?.length ? place.images : (place.image ? [place.image] : [])`

---

## Map Screen Fix

### `frontend/app/(tabs)/map.tsx`
- **Bug:** Used raw GeoJSON features — no typed coordinate extraction, wrong lat/lng order
- **Fix:** Uses `NormalizedMapFeature[]` from `fetchMapGeoJSON`, markers use `f.coordinate.lat` / `f.coordinate.lng`

---

## Search Screen Fix

### `frontend/app/(tabs)/search.tsx`
- **Bug:** `doSearch` sent `{ q, city_id }` — backend 422
- **Fix:** Changed to `{ query: q, city_id }`

---

## Phase Status

| Phase | Description | Status |
|-------|-------------|--------|
| 5 | React Query migration (feed/map/search/detail) | 🔴 open |
| 6 | API contract fixes | ✅ complete |
| 7 | Rendering + state fixes | ⚠️ code complete — not runtime verified |
| 8–9 | Honest empty/error/loading states + diagnostics | 🔴 open |
| 10 | Normalization tests | 🔴 open |

---

## Current Verified Runtime Status

> Code-level fixes applied. Runtime verification not yet performed — app was not launched against production backend during this session.

| Screen | Code Fix Applied | Runtime Verified |
|--------|-----------------|-----------------|
| Feed | ✅ initCities wired, normalizePlaceOut wired | ❌ not verified |
| Map | ✅ lat/lng sent, NormalizedMapFeature used | ❌ not verified |
| Search | ✅ query param fixed, normalizePlaceOut wired | ❌ not verified |
| Detail | ✅ allImages uses place.image, menu unwrapped | ❌ not verified |
| Saves | ✅ no contract changes required | ❌ not verified |

---

## DB State (as of migration)
- 8,922 places
- 91 cities
- 13,248 images
- 0 menu items
- Berkeley: 1,068 active places
