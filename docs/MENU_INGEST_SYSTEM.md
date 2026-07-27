# MENU_INGEST_SYSTEM

**Responsibility:** End-to-end pipeline from place selection → menu extraction → DB write.

---

## Pipeline Layers

```
Place selection (batch script)
  → MasterDataOrchestrator.ensure_place()
    → MenuOrchestrator.run_for_place()
      → Source priority: Grubhub → CSV → Provider (Toast/etc) → HTML fallback
      → MenuWriter.write_items()
        → menu_items table
      → MenuImageBridge
        → place_images table (via Phase 3 classifier)
    → materialize_menu_truth()
      → has_menu flag updated on Place
```

---

## Entry Points

| Script | Purpose |
|--------|---------|
| `scripts/run_phase4_batch.py` | Batch extraction (200–500 places at a time) |
| `scripts/run_menu_worker.py` | Continuous worker loop |
| `scripts/discover_menu_sources.py` | Probe Place.website → populate menu_source_url |
| `app/services/menu/menu_ingest.py` | Single-place programmatic entry |

---

## Source Priority

1. **Grubhub** — live fetch from `grubhub_url` or website if contains `grubhub.com`
2. **CSV** — `place.menu_csv_path` if set
3. **Provider extractors** — Toast, ChowNow, Clover, Square, Popmenu (via URL detection)
4. **HTML fallback** — JSON-LD → structured HTML parsing
5. **Google** — fallback only, marked `fallback_used=true`

---

## DB Tables Written

| Table | Written by | Key fields |
|-------|-----------|------------|
| `menu_items` | MenuWriter | name, section, price_cents, fingerprint, place_id |
| `places` | materialize_menu_truth | has_menu, menu_source_url |
| `place_images` | MenuImageBridge | url, content_type, quality_score, visibility_status |

---

## Connection Pool

- `pool_size=20`, `max_overflow=40`, `pool_recycle=1800`, `pool_pre_ping=True`
- File: `app/db/session.py`

---

## Batch Run Command

```bash
cd backend
python scripts/run_phase4_batch.py --limit 200 --priority smart
```

Priority options: `grubhub | provider | web | all | smart`

---

## Rules

- Each place processed once per batch run (deduped by place_id)
- Commit every 10 places
- Checkpoint log every 50 places
- Menu items only written if `validated_items >= MIN_CANONICAL_ITEM_COUNT (2)`
- Item images → Phase 3 pipeline (classifier → visibility → primary selector). No bypass.
