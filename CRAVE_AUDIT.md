# CRAVE DATA RECOVERY AUDIT

Generated: 2026-04-16

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

| Endpoint | URL | Actual response shape | Frontend expects | Mismatch | Bug |
|----------|-----|----------------------|-----------------|---------|-----|
| cities | GET /api/v1/cities | `[{id, name, slug, lat, lng}]` | `CityOut[]` | ✅ match | none |
| feed | GET /api/v1/places?city_id=X | `{total, page, page_size, items:[PlaceOut]}` | `PlacesResponse` | ✅ match | none if city selected |
| trending | GET /api/v1/trending?city_id=X | `{total, page, page_size, items:[PlaceOut]}` | `{items:PlaceOut[]}` → `.items` | ✅ match (unwrapped correctly) | none |
| place detail | GET /api/v1/place/{id} | `{id,name,images:[url],primary_image_url,...}` | `PlaceOut` | ✅ match | none |
| menu | GET /api/v1/places/{id}/menu | `{items:[]}` (object) | `MenuItem[]` (array) | ❌ SHAPE MISMATCH | menuItems.slice crash |
| map geojson | GET /api/v1/map/geojson | requires `lat`,`lng`,`city_id` | called with `city_id` only | ❌ MISSING REQUIRED PARAMS | 422 → map error banner |
| search | GET /api/v1/search | requires `query`, returns `{total,page,page_size,items}` | sends `q`, expects `PlaceOut[]` | ❌ TWO MISMATCHES | 422 on search |
| search items | (in search response) | field: `primary_image` | field: `primary_image_url` | ❌ FIELD NAME MISMATCH | no images in search |

---

## ROOT CAUSES

### 1. Feed empty on first install
**Classification: FILTER_MISMATCH**
- `selectedCity` is null on first install (no city persisted to AsyncStorage)
- `fetchPlaces` only fires when `selectedCity != null` (index.tsx)
- Feed shows empty skeleton indefinitely
- Fix: auto-select first city after cities load if nothing persisted

### 2. Map "Could not load places"
**Classification: REQUEST_FAILURE**
- File: `src/api/map.ts:22`
- `fetchMapGeoJSON({ city_id })` sends no `lat`/`lng`
- Backend: `map.py` — both `lat: float = Query(...)` and `lng: float = Query(...)` are required
- FastAPI returns 422 before function runs
- Map screen catch at `map.tsx:54` sets `mapError = true`
- Fix: pass `selectedCity.lat` / `selectedCity.lng` in the request

### 3. menuItems.slice crash
**Classification: PARSING_FAILURE**
- File: `src/api/menu.ts:12` — typed as returning `MenuItem[]` but API returns `{items: MenuItem[]}`
- File: `app/place/[id].tsx:134` — `menuItems.slice(0, 5)` crashes when `menuItems` is object
- Axios returns `{items:[]}` as `data`, frontend stores it as `menuItems` (object not array)
- `menuItems.slice` → TypeError: not a function
- Also: DB has 0 menu items — even after fix, menu is empty
- Fix: unwrap `data.items` in `getPlaceMenu`

### 4. Search never returns results
**Classification: REQUEST_FAILURE + PARSING_FAILURE (two bugs)**
- Bug A: `src/api/search.ts:7` — sends `q` param, backend expects `query` → 422 every search
- Bug B: `src/api/search.ts:10` — typed as `PlaceOut[]` but API returns `{total,page,page_size,items}`
- Bug C: search `PlaceCardOut` uses field `primary_image`, frontend `PlaceOut` has `primary_image_url`
- Fix: rename `q` → `query`, unwrap `.items`, remap image field

### 5. City mismatch
**Classification: FILTER_MISMATCH**
- City IDs are UUIDs from DB — correctly used everywhere as `selectedCity.id`
- No slug/name mismatch in queries
- Root issue is just null selectedCity on first load (see #1)

---

## PHASE 3 — CANONICAL MODELS

```typescript
NormalizedPlace {
  id: string
  name: string
  city_id: string
  lat: number | null
  lng: number | null
  rank_score: number
  price_tier: number | null
  primary_image_url: string | null
  images: string[]
  category: string
  categories: string[]
  address: string | null
  website: string | null
  grubhub_url: string | null
  has_menu: boolean
}

NormalizedMenuItem {
  id: string
  name: string
  price: number | null
  description: string | null
  category: string | null
}

NormalizedMenuResponse {
  items: NormalizedMenuItem[]
}

NormalizedCity {
  id: string
  name: string
  slug: string
  lat: number | null
  lng: number | null
}

NormalizedMapFeature {
  id: string
  name: string
  coordinate: { latitude: number; longitude: number }
  tier: string
  rank_score: number
  primary_image_url: string | null
}
```

---

## PHASE 4 — FIX PLAN

Priority order: menu crash → search fix → map fix → city auto-select → normalization layer

### Fix 1: `src/api/menu.ts`
- Unwrap `data.items` instead of returning `data` directly
- API returns `{ items: MenuItem[] }` not `MenuItem[]`

### Fix 2: `src/api/search.ts`
- Rename param `q` → `query`
- Unwrap `data.items` from paginated response
- Add `primary_image` → `primary_image_url` remap

### Fix 3: `src/api/map.ts`
- `fetchMapGeoJSON` must accept `lat` and `lng`
- Map screen passes `selectedCity.lat` / `selectedCity.lng`

### Fix 4: `src/stores/cityStore.ts` + init
- Auto-select first city after cities load if `selectedCity` is null
- Add `initCities` action that fetches + auto-selects

### Fix 5: Normalization layer
- New file: `src/api/normalize.ts`
- `normalizePlaceOut`, `normalizeMenuItems`, `normalizeMapFeatures`

### Fix 6: Color
- `src/constants/colors.ts` — change `primary` from red to eye-friendly blue
- Research: #4A90D9 (soft medium blue, low saturation, comfortable for long use)

---

## PHASE 5 — SUCCESS CRITERIA

- [ ] Feed shows real restaurants after city auto-selected
- [ ] Map loads pins without error
- [ ] Search returns results with correct param name
- [ ] Place detail never crashes on menu
- [ ] Images show in search results
- [ ] All data goes through normalization
