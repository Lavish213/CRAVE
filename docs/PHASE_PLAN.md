# PHASE_PLAN

**Responsibility:** Current system phase status and next steps.

---

## Completed Phases

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | SQLite → PostgreSQL migration | ✅ DONE |
| 2 | Backend API contracts + frontend normalization | ✅ DONE |
| 3 | Image classification system (72,226 images) | ✅ DONE |
| 3.1 | Feed ranker + proximity + distance_miles + tier | ✅ DONE |
| 3.2 | Scoring formula fix + tier distribution | ✅ DONE |
| 3.3 | API consistency (all endpoints) + saves auth | ✅ DONE |

---

## Phase 3 Final State (DB Verified 2026-04-23)

- Images total: 72,226
- content_type NULL: 0
- quality_score NULL: 0
- candidate_primary: 14,070 (19.5%)
- gallery_only: 58,156 (80.5%)
- hidden primaries: 0
- primary == Google rank-0: 14,070/14,073 (100%)

---

## Current Phase: 4 — Menu Extraction System

### Goal
Populate `menu_items` table. Currently: 0 rows.

### Priority Queue
1. Grubhub-linked places (structured payload)
2. Provider-detected places (Toast, ChowNow, Clover, Square, Popmenu URLs)
3. All active places with websites (HTML extraction)

### Phase 4 Batch Command
```bash
cd backend
python scripts/run_phase4_batch.py --limit 200 --priority smart          # preview only
python scripts/run_phase4_batch.py --limit 200 --priority smart --run    # executes
```
`--limit` is required (max 200) and, without `--run`, this only previews
the target count and a sample of place IDs/names -- added after a
contamination incident on the web/provider extraction path this script
drives (see `.agent-bridge/STATE.md` for the incident and fix).

### Phase 4 Success Criteria
- [ ] menu_items > 0
- [ ] places_with_menus / active_places coverage > 5%
- [ ] No NULL fingerprints in menu_items
- [ ] No crashes in batch run
- [ ] Item images routed through Phase 3 pipeline

---

## Phase 5 (Planned): Extractor System — Real Platform Data

### Goal
Replace website scraping with direct platform API access:
- Toast API → menu hierarchy + item images
- ChowNow API → menu items
- Popmenu → structured data

### Architecture (from CRAVE_PHASE_4_MASTER)
```
Extraction Priority:
1. Platform extractors (Toast, ChowNow, Popmenu)
2. JSON-LD / schema.org structured data
3. HTML parsing
4. Google fallback (marked fallback_used=true)
```

### Known Bugs to Fix Before Phase 5
- `toast_extractor.py`: uses `price=` (str) → must convert to `price_cents` (int)
- `toast_extractor.py`: `item.imageUrl` not extracted → add extraction
- `MenuImageBridge`: bridge from item.image_url → ImageIngestService missing

---

## Data Coverage Gaps (blockers)

| Gap | Severity | Required Fix |
|-----|----------|-------------|
| 22 cities with 0% images | HIGH | Run Google enrichment for non-enriched cities |
| Specific category < 60% (35.5%) | HIGH | Google enrichment for top 10 cities |
| price_tier = NULL for all places | MEDIUM | Price data source (Yelp / Google / OSM) |
| menu_items = 0 | CRITICAL | Phase 4 extraction run |

---

## Architecture Invariants (NEVER change without full DB verification)

- Image ordering: `rowid ASC` — not UUID, not created_at
- Re-election step after any image backfill: MANDATORY
- Pool: `pool_size=20, max_overflow=40`
- One primary per place, never hidden
