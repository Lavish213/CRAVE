# HEALTH INGEST AUDIT
Generated: 2026-04-16

---

## PHASE 1 — SYSTEM AUDIT

### Existing Ingestion Systems

| File | Entry Point | Extracts | Ignores | Output | Status |
|------|-------------|----------|---------|--------|--------|
| `app/services/ingest/google_places_ingest.py` | `GooglePlacesIngest.scan_grid()` | name, lat, lng, vicinity, place_id | types[], website, formatted_address, rating, phone | discovery_candidates via discovery_service | ACTIVE (types[] gap) |
| `app/services/discovery/osm_overpass.py` | `fetch_osm_pois()` | name, lat, lon, address, phone, website, category_hint, amenity/cuisine tags | opening_hours, operator | discovery_candidates via candidate_store_v2 | ACTIVE (cuisine never normalized) |
| `app/services/discovery/promote_service_v2.py` | `promote_candidate_v2()` | reads DiscoveryCandidate → creates Place | null lat/lng validation before promotion | places table | ACTIVE (no coord guard) |
| `app/services/discovery/discovery_service.py` | `ingest_candidate_v2()` | normalizes all fields, resolves city, resolves category | - | discovery_candidates | ACTIVE |
| `app/services/ingest/candidate_writer.py` | `CandidateWriter.write()` | batch upsert by external_id | - | discovery_candidates | ACTIVE |
| `app/db/models/discovery_candidate.py` | model | all candidate fields incl. category_hint, lat, lng, website | - | - | ACTIVE |
| `app/services/discovery/nominatim_client.py` | `search_place()`, `reverse_geocode()` | lat/lon from address query | - | dict (lat, lon) | DEAD — never called |
| `app/services/discovery/health_inspections_connector.py` | `run()` | name, address, lat, lon, phone | city resolution, geocoding fallback | discovery_candidates (stub) | STUB |
| `app/services/discovery/candidate_store_v2.py` | `upsert_discovery_candidate_v2()` | full candidate upsert with dedup | - | discovery_candidates | ACTIVE |
| `app/scripts/seed_categories.py` | `seed_categories()` | 31 canonical categories | - | categories table | ACTIVE |

### How candidates become places
1. `ingest_candidate_v2()` / `CandidateWriter.write()` → writes to `discovery_candidates`
2. `promotion_orchestrator_v2.py` → filters candidates with `confidence_score >= 0.72`, `resolved=False`, `blocked=False`
3. `promote_candidate_v2()` → creates `Place` (if not exists by city_id+name), emits claims, resolves truths, marks candidate as resolved

### Where deduplication happens
- `candidate_store_v2.py`: unique constraint on `(external_id, source)` and `(city_id, name, lat, lng)`
- `promotion_orchestrator_v2.py`: skips already-resolved candidates
- `promote_service_v2.py`: queries Place by `(city_id, name)` before creating

### Where category assignment happens
- `discovery_service._resolve_category()` — matches `category_hint` → Category via `_CATEGORY_ALIASES` dict + fuzzy token overlap
- OSM: `category_hint` set from `amenity > shop > cuisine` tags but never fully normalized
- Google: `category_hint` not set at all (types[] ignored)

### Where lat/lng validation happens
- `truth_engine.py`: validates range `lat [-90,90]`, `lng [-180,180]`
- `promote_service_v2.py`: NO null check — creates Place with null coords if candidate has none
- `promotion_orchestrator_v2.py`: NO coord filter before batch promotion

---

## PHASE 2 — GAP ANALYSIS

| Gap | Severity | Layer | Missing Logic |
|-----|----------|-------|---------------|
| No health department connector | Critical | ingest | No fetcher for city/county open data health endpoints or CSV files |
| No structured address ingestion from external datasets | Critical | ingest | Health data arrives as address strings, no geocoding flow |
| Nominatim never called before promotion | Critical | promote | `promote_service_v2` creates Place with null coords if candidate missing lat/lng |
| Google types[] never extracted | Major | ingest | `_convert_place` discards the types array entirely — category_hint always null for Google places |
| OSM category_hint never mapped to canonical categories | Major | normalize | `_CATEGORY_ALIASES` in discovery_service missing OSM cuisine/amenity values |
| No dedup across sources for health data | Major | ingest | Health records have different external_id format — need SHA1 hash strategy |
| Health inspections connector is stub only | Major | ingest | `health_inspections_connector.py` has field mapping but no fetcher, no geocoder, never called |
| No geocoding fallback path for address-only records | Major | normalize | Records with address but no coords fall through with null lat/lng |
| No scheduler job for health ingestion | Minor | integration | No APScheduler entry for periodic health data refresh |

---

## PHASE 3 — ARCHITECTURE PLAN

### File Map

| File | Role |
|------|------|
| `app/services/discovery/health_connector.py` | Fetch raw health data from URL (CSV or JSON API) |
| `app/services/discovery/health_parser.py` | Extract structured fields from raw health records |
| `app/services/discovery/health_normalizer.py` | Clean, standardize, build category_hint |
| `app/services/discovery/health_geocoder.py` | Resolve lat/lng via Nominatim if missing |
| `app/services/discovery/health_writer.py` | Write normalized records to discovery_candidates only |

### Data Flow

```
health source (CSV URL / open data API)
  → health_connector.py  (fetch raw bytes / rows)
  → health_parser.py     (extract name, address, city, zip, category fields)
  → health_normalizer.py (clean strings, derive category_hint)
  → health_geocoder.py   (call Nominatim if lat/lng missing)
  → health_writer.py     (call ingest_candidate_v2 → discovery_candidates)
```

### Canonical Candidate Contract

```python
{
  "source": "health_dept",
  "external_id": "health:{sha1_of_name_address}",
  "name": str,
  "address": str,
  "city": str,
  "state": str,
  "zip": str,
  "lat": float | None,
  "lng": float | None,
  "category_hint": str,  # e.g. "restaurant", "cafe"
  "confidence": 0.75,
  "raw_payload": dict
}
```

### Deduplication Strategy
- Primary key: `external_id = "health:{sha1(name.lower() + address.lower())}"`
- Matched against `(external_id, source)` unique constraint in discovery_candidates
- Cross-source dedup handled by `candidate_store_v2` name+city+location bucket

### Geocoding Strategy
- If record has lat/lng → use directly
- If missing → call `nominatim_client.search_place(query=f"{name} {address} {city} {state}")`
- If Nominatim fails → set lat=None, lng=None, confidence=0.5 (will not promote without coords)

### Integration with Existing Pipeline
- health_writer → `ingest_candidate_v2()` (same entry point as Google and OSM)
- Promotion: existing `promotion_orchestrator_v2` picks up health candidates automatically when `confidence_score >= 0.72`
- Category resolution: existing `_resolve_category` in discovery_service handles category_hint

---

## PHASE 6 — VALIDATION CHECKLIST

- [ ] All records write to `discovery_candidates` only
- [ ] No direct writes to `places` table
- [ ] external_id follows `health:{sha1}` format
- [ ] Records missing lat/lng after Nominatim → confidence set to 0.5, not promoted
- [ ] Records with geocoded coords → confidence 0.75
- [ ] Existing Google/OSM ingestion unaffected
- [ ] Script runnable standalone: `python -m app.scripts.run_health_ingest`
- [ ] Compatible with existing promotion_orchestrator_v2 scheduler job

---

## FIX LOG (applied this session)

### Fix 1: Google Places — extract types[]
- File: `app/services/ingest/google_places_ingest.py`
- Added: `_best_type_hint(types)` maps types[] to category_hint
- Added: `category_hint` field in `_convert_place` output

### Fix 2: Category normalization
- File: `app/services/discovery/discovery_service.py`
- Expanded `_CATEGORY_ALIASES` with full Google types[] and OSM cuisine/amenity mappings

### Fix 3: Nominatim fallback in promote_service_v2
- File: `app/services/discovery/promote_service_v2.py`
- Before Place creation: if lat/lng null, call nominatim_client.search_place()
- If still null after geocoding: return None (do not promote)

### Health Ingestion System
- New: `app/services/discovery/health_connector.py`
- New: `app/services/discovery/health_parser.py`
- New: `app/services/discovery/health_normalizer.py`
- New: `app/services/discovery/health_geocoder.py`
- New: `app/services/discovery/health_writer.py`
- New: `app/scripts/run_health_ingest.py`
