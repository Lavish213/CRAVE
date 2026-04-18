# CRAVE DATA RECOVERY AUDIT

Generated: 2026-04-16  
Last updated: 2026-04-16

---

## ENV / API BASE

- `EXPO_PUBLIC_API_URL` = `https://crave-production.up.railway.app` ✅
- `EXPO_PUBLIC_API_KEY` = set ✅
- client.ts:3 — localhost fallback exists: `?? 'http://localhost:8000'` (safe, env is set)
- No hardcoded URLs beyond fallback
- Header sent as `x-api-key` (lowercase), backend auth checks — needs verification

---

## DATABASE STATE

- places: 8,922 total / 8,921 active with valid coords
- cities: 91 rows
- place_images: 13,248 rows
- menu_items: **0 rows** — no menu data in DB
- Berkeley: 1,068 active places

---

## ENDPOINT MISMATCH TABLE

| Endpoint | URL | Actual response shape | Frontend expects | Mismatch | Status |
|----------|-----|----------------------|-----------------|---------|--------|
| cities | GET /api/v1/cities | `[{id, name, slug, lat, lng}]` | `CityOut[]` | ✅ match | fixed |
| feed | GET /api/v1/places?city_id=X | `{total, page, page_size, items:[PlaceOut]}` | `PlacesResponse` | ✅ match | fixed |
| trending | GET /api/v1/trending?city_id=X | `{total, page, page_size, items:[PlaceOut]}` | `{items:PlaceOut[]}` | ✅ match | fixed |
| place detail | GET /api/v1/place/{id} | `{id,name,images:[url],primary_image_url,...}` | `PlaceOut` | ✅ match | fixed |
| menu | GET /api/v1/places/{id}/menu | `{items:[]}` (object) | `MenuItem[]` (array) | ❌ SHAPE MISMATCH → fixed | fixed — unwrapped `data.items` |
| map geojson | GET /api/v1/map/geojson | requires `lat`,`lng`,`city_id` | called with `city_id` only | ❌ MISSING REQUIRED PARAMS → fixed | fixed — sends `lat`/`lng` |
| search | GET /api/v1/search | requires `query`, returns `{total,page,page_size,items}` | sent `q`, expected `PlaceOut[]` | ❌ TWO MISMATCHES → fixed | fixed — `q→query`, unwrap `.items` |
| search items | (in search response) | field: `primary_image` | field: `primary_image_url` | ❌ FIELD NAME MISMATCH → fixed | fixed — normalizePlaceOut handles both |

---

## ROOT CAUSES

### 1. Feed empty on first install
**Classification: FILTER_MISMATCH** — FIXED  
- `selectedCity` is null on first install (no city persisted to AsyncStorage)
- `fetchPlaces` only fires when `selectedCity != null`
- Fix: `initCities()` auto-selects SF (fallback: first city) if `selectedCity` is null; `index.tsx` calls `initCities()` when city is null before returning

### 2. Map "Could not load places"
**Classification: REQUEST_FAILURE** — FIXED  
- `fetchMapGeoJSON({ city_id })` sent no `lat`/`lng` → backend 422
- Fix: passes `selectedCity.lat` / `selectedCity.lng`; returns `NormalizedMapFeature[]`; coordinate extracted as `{ lat: coords[1], lng: coords[0] }`

### 3. menuItems.slice crash
**Classification: PARSING_FAILURE** — FIXED  
- API returns `{items: MenuItem[]}`, frontend stored as `menuItems` (object), `.slice()` crashed
- Fix: `getPlaceMenu` unwraps `data.items`; DB has 0 menu items so menu section stays empty but no crash

### 4. Search never returns results
**Classification: REQUEST_FAILURE + PARSING_FAILURE** — FIXED  
- Bug A: sent `q` param, backend expects `query` → 422
- Bug B: expected `PlaceOut[]` but API returns `{total,page,page_size,items}`
- Bug C: search returns `primary_image`, normalization expected `primary_image_url`
- Fix: `query` param, unwrap `.items`, `normalizePlaceOut` handles both field names

### 5. Images not rendering
**Classification: NORMALIZATION MISSING** — FIXED (code-level)  
- `normalizePlaceOut` was created but never wired into `fetchPlaces`, `fetchTrending`, `fetchPlaceDetail`
- All UI components used different field names (`primary_image_url`, `primary_image`, `images[0]`)
- Fix: canonical `image` field on `PlaceOut` with fallback chain; all components use `place.image`

### 6. City auto-select / first load
**Classification: STORE MISSING ACTION** — FIXED (code-level)  
- No `initCities()` — cities never fetched on first install, `selectedCity` stayed null forever
- Fix: `initCities()` added to `cityStore`, called from `_layout.tsx` and `index.tsx`

---

## CANONICAL MODELS (as implemented)

```typescript
PlaceOut {
  id: string
  name: string
  city_id: string
  rank_score: number
  category: string | null
  categories: string[]
  address: string | null
  lat: number | null
  lng: number | null
  image: string | null              // canonical — primary_image_url || primary_image || images[0]
  primary_image_url: string | null  // kept for compat (equals image)
  images: string[]
  website: string | null
  grubhub_url: string | null
  has_menu: boolean
  price_tier: number | null
}

NormalizedMapFeature {
  id: string
  name: string
  coordinate: { lat: number; lng: number }
  tier: 'elite' | 'trusted' | 'solid' | 'default'
  rank_score: number
  price_tier: number | null
  image: string | null
  has_menu: boolean
}

NormalizedCity {
  id: string
  name: string
  slug: string
  lat: number | null
  lng: number | null
}

MenuItem {
  id: string
  name: string
  price: number | null
  description: string | null
  category: string | null
}
```

---

## PHASE STATUS

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Audit | ✅ complete |
| 2 | Backend migration (SQLite → PostgreSQL) | ✅ complete |
| 3 | Canonical models | ✅ complete |
| 4 | Fix plan | ✅ complete |
| 5 | React Query migration (feed/map/search/detail) | 🔴 open |
| 6 | API contract fixes (menu, search, map, normalization wiring) | ✅ complete |
| 7 | Rendering + state fixes (feed first load, images, map markers) | ⚠️ code complete — not runtime verified |
| 8–9 | Honest empty/error/loading states + dev diagnostics | 🔴 open |
| 10 | Normalization tests | 🔴 open |

---

## CURRENT VERIFIED RUNTIME STATUS

> Code-level fixes applied. Runtime verification not yet performed (app not launched against production backend during this session).

| Screen | Code Fix Applied | Runtime Verified |
|--------|-----------------|-----------------|
| Feed | ✅ initCities wired, normalizePlaceOut wired | ❌ not verified |
| Map | ✅ lat/lng sent, NormalizedMapFeature used | ❌ not verified |
| Search | ✅ query param fixed, normalizePlaceOut wired | ❌ not verified |
| Detail | ✅ allImages uses place.image, menu unwrapped | ❌ not verified |
| Saves | ✅ no contract changes required | ❌ not verified |

---

## PHASE 7 SUCCESS CRITERIA

- [ ] Feed shows real restaurants after cold launch with no persisted city
- [ ] Map loads pins without error banner
- [ ] Search returns results for a real query (e.g. "pizza")
- [ ] Place detail opens without crash, menu section empty but no TypeError
- [ ] Images render in feed cards, search results, and detail gallery
- [ ] All data confirmed flowing through normalizePlaceOut
