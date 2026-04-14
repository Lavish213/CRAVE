# CRAVE Production Finalization — Design Spec
**Date:** 2026-04-13  
**Approach:** Option A — Targeted Surgical Fixes (additive only, zero regressions)

---

## Problem Statement

CRAVE is architecturally strong but intellectually weak. Three core gaps:

1. **Scoring is flat** — `recompute.py` sums fields that are always `0.0`. Result: ~0.02 avg score, random ranking.
2. **Map output is not Mapbox-compatible** — `/map` returns a flat dict, not a `FeatureCollection`.
3. **No Hit List feature** — user saves, suggestions, and social intake don't exist.

---

## Architecture (Option A — Additive Only)

All changes are additive. No existing file is deleted, replaced, or broken.

The only targeted fix is `recompute.py` — a surgical rewrite of the scoring formula.

Everything else is new modules bolted onto the existing system.

---

## Section 1 — Scoring Fix (Multi-Source, City-Aware)

### Root Cause

`recompute.py::_compute_master_score()` computes:
```
base = confidence_score + operational_confidence + local_validation - hype_penalty + 0.15*(has_menu)
```
All fields default to `0.0` and are never populated by any active pipeline. Result: 84% of places score `0.0`, 16% score `~0.15`. Average ≈ `0.024`.

### Fix

Replace the scoring formula with a 9-signal, city-aware weighted model. Batch-query all signal counts before scoring. Pure function, fully testable.

---

### 9 Signals (All Normalized 0–1)

| Signal | Source | Formula |
|---|---|---|
| `menu_score` | `menu_items` table | `min(menu_item_count / 50, 1.0)` |
| `image_score` | `place_images` table | `min(image_count / 10, 1.0)` |
| `completeness_score` | `places` model fields | avg of: `[name, lat+lng, image, menu or website]` |
| `recency_score` | `place.updated_at` | `max(0, 1.0 - days_since_update / 90)` |
| `app_score` | `grubhub_url`, `menu_source_url` | `1.0` if any provider URL present, else `0.0` |
| `hitlist_score` | `HitlistSave` table (future) | velocity score from aggregator; `0.0` until hitlist is live |
| `creator_score` | `PlaceSignal` with `source=social` (future hook) | `0.0` until social signals are wired |
| `awards_score` | `PlaceSignal` with `source=awards` (future hook) | `0.0` until awards data ingested |
| `blog_score` | `PlaceSignal` with `source=blog` (future hook) | `0.0` until blog data ingested |

**Missing data rule:** if a signal is `0.0` because no data exists (not because the place is bad), that signal's weight is redistributed proportionally to the signals that DO have data. The total weight always sums to 1.0. This prevents empty-signal places from being unfairly penalized.

---

### City-Aware Weight Profiles

**New file:** `app/services/scoring/city_weight_profiles.py`

Profiles are declared as named dicts, never hardcoded inline. Default profile used when no city match.

```python
DEFAULT_PROFILE = {
    "menu_score":        0.22,
    "image_score":       0.18,
    "completeness_score":0.12,
    "recency_score":     0.10,
    "app_score":         0.13,
    "hitlist_score":     0.10,
    "creator_score":     0.08,
    "awards_score":      0.04,
    "blog_score":        0.03,
}

CITY_PROFILES = {
    "nyc":         {**DEFAULT_PROFILE, "awards_score": 0.12, "blog_score": 0.08, "menu_score": 0.18, "creator_score": 0.04},
    "los_angeles": {**DEFAULT_PROFILE, "creator_score": 0.16, "hitlist_score": 0.14, "awards_score": 0.02},
    "new_orleans": {**DEFAULT_PROFILE, "blog_score": 0.12, "awards_score": 0.08, "app_score": 0.10},
}
# All profiles must sum to 1.0 — validated at import time
```

City slug is resolved from `place.city_id` → `City.slug` at recompute time.

---

### Final Score Formula

```
active_signals = {k: v for k, v in signals.items() if v > 0.0 or data_exists(k)}
weights = get_city_profile(city_slug)
weights = redistribute_missing(weights, active_signals)  # re-normalize
final_score = sum(signals[k] * weights[k] for k in weights)
final_score += uuid_entropy_tiebreak(place_id)   # ≤ 0.000001
```

---

### Batch Queries (no per-place queries)

```sql
-- image counts
SELECT place_id, COUNT(*) FROM place_images GROUP BY place_id

-- menu item counts  
SELECT place_id, COUNT(*) FROM menu_items WHERE is_active = 1 GROUP BY place_id
```

Both run once per recompute batch. Results loaded into dicts keyed by `place_id` before scoring loop begins.

---

**Files:**
- `app/services/scoring/place_score_v3.py` — NEW, pure scoring function (takes pre-fetched signal context)
- `app/services/scoring/city_weight_profiles.py` — NEW, all weight profiles
- `app/services/scoring/signal_context.py` — NEW, dataclass holding pre-fetched batch signal data
- `app/workers/recompute_scores_worker.py` — add batch signal fetch before loop, pass context to scorer

---

## Section 2 — Social Intelligence Layer (Hooks Only)

**New module:** `app/services/social/`

### Hard Rules

- **Non-authoritative**: social parsing creates signals only — never canonical place truth
- **No crawling**: URL and text parsing only, zero live API calls
- **No direct ranking boosts**: social signals feed weak metadata, not master_score directly
- **No truth writes**: output is stored as PlaceSignal records or attached to HitlistSave, not to PlaceTruth

### Files

| File | Source | Role |
|---|---|---|
| `app/services/social/__init__.py` | NEW | module init |
| `app/services/social/platform_detect.py` | Legacy + improved | Detects tiktok/instagram/youtube/google_maps/grubhub/yelp/doordash/generic from URL |
| `app/services/social/url_normalize.py` | Legacy + improved | Strips utm_*, fbclid, igshid, gclid; normalizes scheme/host casing, removes fragments |
| `app/services/social/caption_parser.py` | Legacy + improved | Extracts hashtags, mentions, 📍 location lines, geo hints (City, ST pattern), place candidates from caption text |
| `app/services/social/extractors/__init__.py` | NEW | — |
| `app/services/social/extractors/tiktok.py` | Legacy + improved | Pulls creator handle + confidence from TikTok URLs. Returns typed dict with `platform`, `creator_handle`, `confidence` (0–1), `source_url` |
| `app/services/social/extractors/instagram.py` | Legacy + improved | Same contract for Instagram |
| `app/services/social/extractors/youtube.py` | Legacy + improved | Same contract for YouTube |

### Output Contract (all extractors)

```python
{
    "platform": str,           # canonical platform name
    "creator_handle": str | None,
    "confidence": float,       # 0.0–1.0, weak signal only
    "source_url": str,         # normalized URL
    "place_name_hint": str | None,  # weak hint only, not authoritative
}
```

---

## Section 3 — Mapbox-Ready Map Endpoint

### Current State

`/map` (existing) returns flat dict with `places` array. Correct, cached, untouched.

### Addition

**New endpoint:** `GET /api/v1/map/geojson`

Returns a proper Mapbox `FeatureCollection` compatible with `Mapbox1.json` source config (`"type": "geojson"`).

### Tier Computation — Percentile-Based (not fixed thresholds)

Fixed thresholds (elite ≥ 0.70 etc.) are dangerous while score distribution is still maturing. Use percentiles computed against the current result set returned by the query:

```
elite   = top 5% of rank_score in result set
trusted = next 15% (5th–20th percentile)
solid   = next 30% (20th–50th percentile)
default = bottom 50%
```

This ensures the map always has a reasonable pin color distribution regardless of current score spread. Once scoring stabilizes, absolute thresholds can replace this.

### GeoJSON Feature Properties

```json
{
  "id": "...",
  "name": "...",
  "tier": "elite|trusted|solid|default",
  "rank_score": 0.0,
  "price_tier": null,
  "primary_image_url": null,
  "has_menu": false
}
```

### Files

- `app/api/v1/routes/map.py` — add `/geojson` sub-route (existing `/` route untouched)
- `app/api/v1/schemas/map.py` — add `GeoJSONFeature`, `GeoJSONFeatureCollection` schemas
- `app/services/query/map_query.py` — add `fetch_places_for_map_geojson()` (wraps existing, adds tier)

---

## Section 4 — Crave's Hit List

### Models (3 new, additive)

**`HitlistSave`** — a user's saved place (raw or resolved)
```
id, user_id, place_name, source_platform, source_url (normalized),
lat, lng, place_id (FK, nullable), resolution_status,
dedup_key, created_at, resolved_at
```

**`HitlistSuggestion`** — user-submitted place recommendation
```
id, user_id, place_name, city_hint, notes, source_platform, source_url,
resolved_place_id (FK, nullable), resolved_at, created_at
```

**`HitlistDedupKey`** — prevents double-saves per user
```
id, user_id, dedup_key (unique per user), created_at
```

### `resolution_status` Enum (on HitlistSave)

```
raw        → just saved, no matching attempted
candidate  → matched to a discovery candidate
matched    → linked to an existing Place
promoted   → the save contributed to a Place being promoted
rejected   → dedup/spam rejected
```

### `source_platform` Values

```
tiktok | instagram | youtube | google_maps | grubhub | yelp | generic | unknown
```

Derived automatically from `platform_detect.py` on intake.

### Dedup Key Priority Order

Computed on intake, exactly in this order:

1. `place_id` — if already resolved
2. `sha256(normalized_source_url)` — if source_url present
3. `sha256(normalized_name + ":" + lat_rounded_4dp + ":" + lng_rounded_4dp)` — if lat/lng present
4. `sha256(normalized_name + ":" + normalized_city)` — fallback

### Hit List Suggestions → Candidate Pipeline

Suggestions **do not** directly create places. They enter the discovery candidate pipeline with:
- `source_type = "hitlist_user_submission"`
- `confidence = 0.0` (must be raised by subsequent signals)
- Requires dedup check, confidence scoring, and optional review threshold before promotion

### Velocity Scoring (HitlistAggregator)

```
recency_score = recent_saves_24h / total_saves    (weight: 0.70)
volume_score  = min(total_saves / 100, 1.0)       (weight: 0.30)
score = recency_score * 0.70 + volume_score * 0.30
```

### API Routes (4 endpoints)

| Route | Method | Auth | Rate Limit |
|---|---|---|---|
| `/hitlist/save` | POST | none (opaque user_id) | 20 saves/min per user |
| `/hitlist/{user_id}` | GET | none | — |
| `/hitlist/delete` | DELETE | none | — |
| `/hitlist/suggest` | POST | none | 10 suggestions/min per user |

Rate limiting: in-memory (same pattern as legacy `rate_limit_memory`), no Redis dependency.

### Minimal Analytics View

Computed on read (no materialized table needed at this stage):
- `GET /hitlist/analytics/summary` — returns: saves_today, top_10_saved_places, unresolved_count, promoted_count

### Files

```
app/db/models/hitlist_save.py          NEW
app/db/models/hitlist_suggestion.py    NEW
app/db/models/hitlist_dedup_key.py     NEW
app/services/hitlist/__init__.py       NEW
app/services/hitlist/save_intake.py    NEW
app/services/hitlist/suggest_intake.py NEW
app/services/hitlist/dedup_engine.py   NEW
app/services/hitlist/aggregator.py     NEW
app/services/hitlist/get_user_hitlist.py NEW
app/services/hitlist/delete_save.py    NEW
app/services/hitlist/analytics.py      NEW
app/services/hitlist/spam_guard.py     NEW (rate limit + dedup enforcement)
app/api/v1/routes/hitlist.py           NEW
app/api/v1/schemas/hitlist.py          NEW
alembic/versions/<hash>_add_hitlist_tables.py  NEW migration
```

---

## Section 5 — Execution Order

1. `place_score_v3.py` + `recompute.py` fix → run recompute → verify score distribution
2. `/map/geojson` + schema additions → test against `Mapbox1.json` config
3. `app/services/social/` layer → unit test all extractors
4. Hitlist DB models + Alembic migration → run migration
5. Hitlist service layer + API routes → smoke test all 4 endpoints + analytics

---

## What Is Explicitly NOT Changing

- `score_place_v2.py` — left as-is (orphaned)
- `score_all_places_v2.py` — left as-is (orphaned, has comment explaining why)
- `GET /map` — untouched
- `image_worker.py` — untouched (Google guard already works)
- `ImageIngestService` — untouched
- All existing API routes — untouched
- All existing DB models — untouched
- All existing workers — untouched except recompute batch fetch

---

## Future Hooks (Do Not Implement Now)

- Social signals → PlaceSignal table (hooks exist, wire up later)
- TikTok/IG live crawling (platform_detect + extractors are the prep)
- Personalization (resolution_status + source_platform make this straightforward later)
- Absolute Mapbox tier thresholds (switch from percentile once scoring stabilizes)
- Hit List → promotion trigger (source_type is already set up for this)
