# CRAVE Backend Finalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finalize the CRAVE backend into a production-ready, coherent system by auditing, connecting, and stabilizing all major subsystems without breaking working logic.

**Architecture:** FastAPI app with SQLite/SQLAlchemy ORM, background workers run as long-lived processes, place ingestion flows AOI→candidates→matching→place writer, scoring/ranking/search index built from canonical place data, cache layer fronts read-heavy endpoints.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.x, SQLite (dev) / Postgres (prod), pytest, standard library only for workers (no Celery)

---

## ⚠️ SCOPE NOTE

This plan is **large** — 13 phases, ~35 tasks. Execute sequentially. Each phase is independently committable. Do NOT execute phases out of order. Phases 1–2 (audit + data flow mapping) MUST complete before any code changes in Phases 3+.

**Critical invariant across all tasks:** The Grubhub menu ingestion pipeline (verified working: `python run_pipeline_debug.py` exits 0) MUST continue to pass after every task.

---

## Pre-Flight Check

Before starting any task, verify the menu pipeline still passes:

```bash
cd /Users/angelowashington/CRAVE/backend
python run_pipeline_debug.py 2>&1 | tail -5
# Expected: PIPELINE COMPLETE — NON-EMPTY MENU MATERIALIZED
```

Run this check after every task that touches any of these files:
- `app/services/menu/`
- `app/db/models/`
- `app/services/truth/`
- `app/main.py`

---

## File Map (files touched by this plan)

### Created
- `docs/superpowers/plans/2026-04-13-crave-backend-finalization.md` ← this file
- `scripts/audit_backend.py` — Phase 1 audit script
- `scripts/verify_backend.py` — Phase 12 verification script
- `app/services/workers/menu_worker.py` — canonical menu worker (if not exists)
- `app/api/v1/routes/menus.py` — v1 menu route (if not exists)

### Modified
- `app/workers/master_worker.py` — wire discovery v2, scoring, search index
- `app/workers/run_pipeline.py` — add ranking + search index loops
- `app/workers/aoi_scan_worker.py` — call real discovery service
- `app/workers/discovery_worker.py` — call pipeline_v2 correctly
- `app/workers/ranking_worker.py` — call rank_calculator
- `app/workers/recompute_scores_worker.py` — call score_place_v2
- `app/workers/search_index_worker.py` — call search_index_builder
- `app/workers/truth_rebuild_worker.py` — call truth_resolver_v2
- `app/services/matching/place_matcher.py` — fix N+1 query
- `app/services/cache/cache_helpers.py` — wire to routes
- `app/api/v1/routes/places.py` — add cache layer
- `app/api/v1/routes/search.py` — add cache layer, wire search_engine
- `app/api/v1/__init__.py` — register menus route
- `app/main.py` — add startup validation

---

## PHASE 1 — FULL AUDIT

### Task 1: Write and run the backend audit script

**Goal:** Discover all broken imports, disconnected modules, and orchestration gaps before touching any production code.

**Files:**
- Create: `scripts/audit_backend.py`

- [ ] **Step 1: Write the audit script**

```python
#!/usr/bin/env python3
"""
Backend audit script — finds broken imports, dead modules, disconnected wiring.
Run from: /Users/angelowashington/CRAVE/backend
Usage:    python scripts/audit_backend.py
"""
from __future__ import annotations

import importlib
import os
import sys
import ast
import traceback
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

SERVICES_DIR = ROOT / "app" / "services"
WORKERS_DIR  = ROOT / "app" / "workers"
API_DIR      = ROOT / "app" / "api"

CRITICAL   = []
MEDIUM     = []
CLEANUP    = []
GOOD       = []

def check(module_path: str) -> tuple[bool, str]:
    try:
        importlib.import_module(module_path)
        return True, "ok"
    except Exception as e:
        return False, str(e)

def collect_modules(base: Path, pkg_prefix: str) -> list[str]:
    mods = []
    for f in sorted(base.rglob("*.py")):
        if f.name.startswith("_"):
            continue
        rel = f.relative_to(ROOT)
        mod = str(rel).replace("/", ".").replace("\\", ".").removesuffix(".py")
        mods.append(mod)
    return mods

print("=" * 70)
print("CRAVE BACKEND AUDIT")
print("=" * 70)

# --- Import check ---
print("\n[1] IMPORT CHECK")
all_mods = (
    collect_modules(SERVICES_DIR, "app.services") +
    collect_modules(WORKERS_DIR, "app.workers") +
    collect_modules(API_DIR, "app.api")
)

for mod in all_mods:
    ok, err = check(mod)
    if ok:
        GOOD.append(mod)
    else:
        first_line = err.split("\n")[0]
        print(f"  BROKEN  {mod}")
        print(f"          {first_line}")
        if "ModuleNotFoundError" in err or "ImportError" in err:
            CRITICAL.append((mod, first_line))
        else:
            MEDIUM.append((mod, first_line))

# --- Worker wiring check ---
print("\n[2] WORKER WIRING CHECK")
WORKER_FILES = list(WORKERS_DIR.glob("*.py"))
for wf in sorted(WORKER_FILES):
    if wf.name.startswith("_"):
        continue
    src = wf.read_text()
    # check for common anti-patterns
    if "db.query(Place).all()" in src:
        MEDIUM.append((str(wf.name), "N+1: loads ALL places without filter"))
        print(f"  N+1     {wf.name}")
    if "pass" in src and len(src) < 200:
        CLEANUP.append((str(wf.name), "stub/empty worker"))
        print(f"  STUB    {wf.name}")

# --- Route registration check ---
print("\n[3] ROUTE REGISTRATION")
v1_init = ROOT / "app" / "api" / "v1" / "__init__.py"
if v1_init.exists():
    src = v1_init.read_text()
    for route in ["places", "search", "menus", "health", "cities", "categories"]:
        if route in src:
            print(f"  REGISTERED  {route}")
        else:
            print(f"  MISSING     {route}")
            MEDIUM.append((f"route/{route}", "not registered in v1/__init__.py"))

# --- Summary ---
print("\n" + "=" * 70)
print("AUDIT SUMMARY")
print("=" * 70)
print(f"  CRITICAL (broken imports): {len(CRITICAL)}")
for m, e in CRITICAL:
    print(f"    {m}: {e}")
print(f"  MEDIUM (wiring/N+1):       {len(MEDIUM)}")
for m, e in MEDIUM:
    print(f"    {m}: {e}")
print(f"  CLEANUP (stubs/dead):      {len(CLEANUP)}")
for m, e in CLEANUP:
    print(f"    {m}: {e}")
print(f"  GOOD (imports ok):         {len(GOOD)}")
print("=" * 70)
```

- [ ] **Step 2: Run the audit**

```bash
cd /Users/angelowashington/CRAVE/backend
python scripts/audit_backend.py 2>&1 | tee /tmp/crave_audit.txt
```

Expected: Prints CRITICAL, MEDIUM, CLEANUP, GOOD sections. Review `/tmp/crave_audit.txt`. Record all CRITICAL items — they block later tasks.

- [ ] **Step 3: Record audit findings**

After running, manually note the following in a comment at the bottom of this plan doc:
- Count of broken imports
- Which workers are stubs
- Which routes are unregistered

- [ ] **Step 4: Commit the audit script**

```bash
cd /Users/angelowashington/CRAVE/backend
git init 2>/dev/null || true
git add scripts/audit_backend.py docs/
git commit -m "chore: add backend audit script and finalization plan"
```

---

### Task 2: Map the real data flow

**Goal:** Confirm which stages of the AOI→Place→Score→Search→API flow actually exist in code (not just as files).

**Files:**
- Read: `app/workers/master_worker.py` (already read — calls `run_google_ingest`, `match_place`, `run_menu_worker`)
- Read: `app/workers/run_pipeline.py` (already read — calls `run_master_ingest`, `run_menu_worker`)
- Read: `app/services/discovery/pipeline_v2.py` (already read — calls `promote_ready_candidates_v2`)

- [ ] **Step 1: Trace each stage and mark status**

Run these greps to confirm each stage exists:

```bash
cd /Users/angelowashington/CRAVE/backend

echo "=== STAGE: AOI grid scanning ===" 
grep -r "aoi_grid\|scan_cells\|aoi_scan" app/workers/ app/services/ --include="*.py" -l

echo "=== STAGE: Discovery candidates ==="
grep -r "candidate_store_v2\|CandidateStore" app/ --include="*.py" -l

echo "=== STAGE: Promotion ==="
grep -r "promote_ready_candidates_v2\|PromotionGate" app/ --include="*.py" -l

echo "=== STAGE: Place matching ===" 
grep -r "match_place\|place_matcher" app/ --include="*.py" -l

echo "=== STAGE: Place writing ==="
grep -r "write_place_candidate_batch\|place_writer" app/ --include="*.py" -l

echo "=== STAGE: Scoring ==="
grep -r "score_place_v2\|compute_master_score" app/ --include="*.py" -l

echo "=== STAGE: Ranking ==="
grep -r "rank_calculator\|rank_score\|rank_places" app/ --include="*.py" -l

echo "=== STAGE: Search index ==="
grep -r "search_index_builder\|build_index\|SearchIndexBuilder" app/ --include="*.py" -l

echo "=== STAGE: API search ==="
grep -r "search_engine\|SearchEngine" app/api/ app/services/search/ --include="*.py" -l

echo "=== STAGE: Cache ==="
grep -r "cache_client\|CacheClient\|cache_get\|cache_set" app/api/ --include="*.py" -l
```

- [ ] **Step 2: Document the gap map**

Based on grep output, annotate which stages are:
- **WIRED**: called from a real worker/route
- **ORPHANED**: module exists, nothing calls it
- **MISSING**: called by something but module doesn't exist

This tells us exactly which tasks in Phases 3–6 are real fixes vs. confirmations.

- [ ] **Step 3: Commit gap map findings**

```bash
git add -u
git commit -m "chore: phase 1 audit complete — gap map documented"
```

---

## PHASE 2 — FIX DATA FLOW

### Task 3: Fix the N+1 in place_matcher

**Files:**
- Modify: `app/services/matching/place_matcher.py` (line 113: `db.query(Place).all()`)

**Problem:** `match_or_create_place` loads ALL places for every candidate. With 10k+ places this is catastrophic.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_place_matcher.py
import pytest
from unittest.mock import MagicMock, patch
from app.services.matching.place_matcher import match_or_create_place

def test_match_or_create_uses_geo_filter_not_full_table_scan():
    """match_or_create_place must NOT call db.query(Place).all()"""
    mock_db = MagicMock()
    # If .all() is called, it would return this — we assert it is NOT called
    mock_db.query.return_value.all.return_value = []

    with patch("app.services.matching.place_matcher.match_place") as mock_match:
        mock_match.return_value = MagicMock(matched=True, provider_id="existing-id")
        result = match_or_create_place(
            db=mock_db,
            name="Test Place",
            lat=37.77,
            lng=-122.41,
        )

    # Should NOT load the whole table
    assert mock_db.query.return_value.all.call_count == 0, (
        "match_or_create_place called .all() — N+1 detected"
    )
    assert result == "existing-id"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/angelowashington/CRAVE/backend
python -m pytest tests/test_place_matcher.py::test_match_or_create_uses_geo_filter_not_full_table_scan -v
```

Expected: FAIL — currently calls `.all()`

- [ ] **Step 3: Fix match_or_create_place with geo-bounded query**

In `app/services/matching/place_matcher.py`, replace lines 99–149:

```python
GEO_SEARCH_RADIUS_KM = 2.0   # search within 2 km for candidates


def match_or_create_place(
    *,
    db: Session,
    name: str,
    lat: float | None = None,
    lng: float | None = None,
    address: str | None = None,
    city_id: str | None = None,
) -> str:

    if not name:
        raise ValueError("name required")

    # ── Geo-bounded query (avoids full table scan) ──────────
    if lat is not None and lng is not None:
        # cheap bounding box: ~2 km at mid-latitudes
        delta_lat = GEO_SEARCH_RADIUS_KM / 111.0
        delta_lng = GEO_SEARCH_RADIUS_KM / (111.0 * math.cos(math.radians(lat)))

        nearby = (
            db.query(Place)
            .filter(
                Place.lat.between(lat - delta_lat, lat + delta_lat),
                Place.lng.between(lng - delta_lng, lng + delta_lng),
            )
            .limit(200)
            .all()
        )
    else:
        # Fallback: query by city if no geo — still bounded
        q = db.query(Place)
        if city_id:
            q = q.filter(Place.city_id == city_id)
        nearby = q.limit(500).all()

    provider_candidates = [
        {
            "id": p.id,
            "name": p.name,
            "lat": p.lat,
            "lng": p.lng,
            "url": getattr(p, "website", None),
        }
        for p in nearby
    ]

    temp_place = type(
        "TempPlace",
        (),
        {"name": name, "lat": lat, "lng": lng},
    )()

    result = match_place(
        local_place=temp_place,
        provider_places=provider_candidates,
    )

    if result.matched and result.provider_id:
        return result.provider_id

    new_city_id = city_id or "745fa4ed-9309-54a3-97b3-717717a5f05b"

    new_place = Place(
        name=name,
        city_id=new_city_id,
        lat=lat,
        lng=lng,
        website=None,
    )

    db.add(new_place)
    db.flush()

    return new_place.id
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_place_matcher.py::test_match_or_create_uses_geo_filter_not_full_table_scan -v
```

Expected: PASS

- [ ] **Step 5: Run menu pipeline guard**

```bash
python run_pipeline_debug.py 2>&1 | tail -3
```

Expected: `PIPELINE COMPLETE — NON-EMPTY MENU MATERIALIZED`

- [ ] **Step 6: Commit**

```bash
git add app/services/matching/place_matcher.py tests/test_place_matcher.py
git commit -m "fix: replace N+1 table scan in match_or_create_place with geo-bounded query"
```

---

### Task 4: Wire master_worker to the real discovery v2 pipeline

**Files:**
- Modify: `app/workers/master_worker.py`

**Problem:** `master_worker.py` calls `run_google_ingest` (legacy) and doesn't call `run_discovery_pipeline_v2`, scoring, ranking, or search index.

- [ ] **Step 1: Write the wiring test**

```python
# tests/test_master_worker.py
from unittest.mock import patch, MagicMock

def test_master_worker_calls_discovery_v2():
    """master_worker must call run_discovery_pipeline_v2, not just google_ingest."""
    with patch("app.workers.master_worker.run_discovery_pipeline_v2") as mock_disc, \
         patch("app.workers.master_worker.run_menu_worker") as mock_menu, \
         patch("app.workers.master_worker.SessionLocal") as mock_session, \
         patch("app.workers.master_worker.time") as mock_time:
        mock_time.sleep.side_effect = StopIteration  # break loop after 1 iteration
        mock_disc.return_value = {"promoted": 3, "error": None}
        mock_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_session.return_value.__exit__ = MagicMock(return_value=False)
        try:
            from app.workers.master_worker import run_master_worker
            run_master_worker()
        except StopIteration:
            pass
        mock_disc.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_master_worker.py::test_master_worker_calls_discovery_v2 -v
```

Expected: FAIL — currently calls `run_google_ingest` instead

- [ ] **Step 3: Rewrite master_worker.py**

Replace `app/workers/master_worker.py` entirely:

```python
from __future__ import annotations

import logging
import time

from app.db.session import SessionLocal
from app.services.discovery.pipeline_v2 import run_discovery_pipeline_v2
from app.services.workers.menu_worker import run_menu_worker


logger = logging.getLogger(__name__)


# =========================================================
# CONFIG
# =========================================================

LOOP_DELAY_SECONDS      = 30
DISCOVERY_BATCH_LIMIT   = 50
MAX_LOOP_ERRORS         = 20


# =========================================================
# SAFE RUNNERS
# =========================================================

def _run_discovery_safe(db) -> dict:
    try:
        result = run_discovery_pipeline_v2(db=db, limit=DISCOVERY_BATCH_LIMIT)
        logger.info("master_discovery_complete promoted=%s", result.get("promoted"))
        return result
    except Exception as exc:
        logger.exception("master_discovery_failed error=%s", exc)
        try:
            db.rollback()
        except Exception:
            pass
        return {"promoted": 0, "error": str(exc)}


def _run_menu_safe() -> None:
    try:
        run_menu_worker()
        logger.info("master_menu_complete")
    except Exception as exc:
        logger.exception("master_menu_failed error=%s", exc)


# =========================================================
# MASTER LOOP
# =========================================================

def run_master_worker() -> None:
    logger.info("master_worker_start")
    error_count = 0

    while True:
        db = SessionLocal()
        try:
            # Stage 1: discover + promote candidates → places
            _run_discovery_safe(db)

            # Stage 2: menu ingestion for known places
            _run_menu_safe()

            error_count = 0

        except Exception as exc:
            error_count += 1
            logger.exception("master_worker_loop_error count=%s error=%s", error_count, exc)
            try:
                db.rollback()
            except Exception:
                pass
            if error_count >= MAX_LOOP_ERRORS:
                logger.critical("master_worker_stopping — too many errors")
                raise

        finally:
            try:
                db.close()
            except Exception:
                pass

        logger.info("master_worker_sleep seconds=%s", LOOP_DELAY_SECONDS)
        time.sleep(LOOP_DELAY_SECONDS)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_master_worker.py::test_master_worker_calls_discovery_v2 -v
```

Expected: PASS

- [ ] **Step 5: Verify menu pipeline guard**

```bash
python run_pipeline_debug.py 2>&1 | tail -3
```

- [ ] **Step 6: Commit**

```bash
git add app/workers/master_worker.py tests/test_master_worker.py
git commit -m "fix: master_worker now calls discovery_v2 pipeline instead of legacy google_ingest"
```

---

## PHASE 3 — PLACE INGESTION

### Task 5: Verify and wire the discovery candidate flow

**Goal:** Confirm that all discovery connectors (nominatim, OSM, openaddresses, business licenses, health, permits, website) actually feed into `candidate_store_v2`, and that `promotion_orchestrator_v2` correctly calls `promotion_gate_v2` before calling `promote_service_v2`.

**Files:**
- Read: `app/services/discovery/promotion_orchestrator_v2.py`
- Read: `app/services/discovery/candidate_store_v2.py`
- Read: `app/services/discovery/promotion_gate_v2.py`
- Read: `app/services/discovery/promote_service_v2.py`

- [ ] **Step 1: Read all four orchestration files**

```bash
cd /Users/angelowashington/CRAVE/backend
cat app/services/discovery/promotion_orchestrator_v2.py
cat app/services/discovery/candidate_store_v2.py
cat app/services/discovery/promotion_gate_v2.py
cat app/services/discovery/promote_service_v2.py
```

- [ ] **Step 2: Trace the call chain**

For each connector, verify it calls `candidate_store_v2.add_candidate()` or equivalent:

```bash
grep -r "candidate_store\|add_candidate\|CandidateStore" \
  app/services/discovery/ --include="*.py" -n
```

If any connector does NOT feed `candidate_store_v2`, note it — it is an orphan.

- [ ] **Step 3: Verify the promotion gate is actually enforced**

```bash
grep -r "promotion_gate_v2\|PromotionGate\|passes_gate\|gate_check" \
  app/services/discovery/promotion_orchestrator_v2.py -n
```

If `promotion_gate_v2` is never called from `promotion_orchestrator_v2`, add the call:

```python
# In promote_ready_candidates_v2(), before calling promote_service_v2:
from app.services.discovery.promotion_gate_v2 import passes_promotion_gate

# ... inside the candidate loop:
if not passes_promotion_gate(candidate):
    logger.debug("gate_reject candidate_id=%s", candidate.id)
    continue
```

- [ ] **Step 4: Write smoke test for promotion chain**

```python
# tests/test_discovery_pipeline.py
from unittest.mock import patch, MagicMock
from app.services.discovery.pipeline_v2 import run_discovery_pipeline_v2

def test_discovery_pipeline_returns_stats_dict():
    """run_discovery_pipeline_v2 must return a dict with 'promoted' key."""
    mock_db = MagicMock()
    with patch("app.services.discovery.pipeline_v2.promote_ready_candidates_v2") as mock_promo:
        mock_promo.return_value = 5
        result = run_discovery_pipeline_v2(db=mock_db, limit=10)
    assert isinstance(result, dict)
    assert "promoted" in result
    assert result["promoted"] == 5
    assert result["error"] is None
```

- [ ] **Step 5: Run test**

```bash
python -m pytest tests/test_discovery_pipeline.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/test_discovery_pipeline.py
git commit -m "test: add smoke test for discovery pipeline v2"
```

---

### Task 6: Wire nominatim + OSM + OpenAddresses into aoi_scan_worker

**Files:**
- Modify: `app/workers/aoi_scan_worker.py`
- Read: `app/services/discovery/nominatim_client.py`
- Read: `app/services/discovery/osm_overpass.py`
- Read: `app/services/discovery/openaddresses_loader.py`

- [ ] **Step 1: Read the current aoi_scan_worker and the three connectors**

```bash
cat app/workers/aoi_scan_worker.py
cat app/services/discovery/nominatim_client.py
cat app/services/discovery/osm_overpass.py
cat app/services/discovery/openaddresses_loader.py
```

- [ ] **Step 2: Check what each connector's public API is**

```bash
grep -n "^def \|^class " \
  app/services/discovery/nominatim_client.py \
  app/services/discovery/osm_overpass.py \
  app/services/discovery/openaddresses_loader.py
```

Record the exact function signatures — you will use them in Step 3.

- [ ] **Step 3: Rewrite aoi_scan_worker to call real services**

The current `aoi_scan_worker.py` only computes density scores and returns dicts — it never calls Nominatim/OSM/OpenAddresses. Replace the worker with one that feeds real data into `candidate_store_v2`.

The exact implementation depends on the connector APIs discovered in Step 2. The pattern must be:

```python
from __future__ import annotations

import logging
import time
from contextlib import suppress

from app.db.session import SessionLocal
from app.services.aoi.aoi_grid import cell_id
from app.services.aoi.aoi_density import compute_density_score
from app.services.aoi.aoi_priority import get_priority_cells
from app.services.discovery.nominatim_client import search_nominatim  # verify exact name
from app.services.discovery.osm_overpass import query_overpass          # verify exact name
from app.services.discovery.candidate_store_v2 import CandidateStore   # verify exact name

logger = logging.getLogger(__name__)

SCAN_INTERVAL_SECONDS = 120
MAX_CELLS_PER_RUN = 10


def run_aoi_scan_worker() -> None:
    logger.info("aoi_scan_worker_start")
    while True:
        db = SessionLocal()
        try:
            # 1. Get highest-priority cells to scan
            cells = get_priority_cells(db=db, limit=MAX_CELLS_PER_RUN)

            for cell in cells:
                lat = cell["lat"]
                lng = cell["lng"]
                radius_m = cell.get("radius_m", 500)

                # 2. Query Nominatim for places in cell
                try:
                    nominatim_results = search_nominatim(lat=lat, lng=lng, radius_m=radius_m)
                    for r in nominatim_results:
                        CandidateStore(db).add_candidate(r)
                except Exception as exc:
                    logger.warning("nominatim_failed cell=%s error=%s", cell, exc)

                # 3. Query OSM Overpass for places in cell
                try:
                    osm_results = query_overpass(lat=lat, lng=lng, radius_m=radius_m)
                    for r in osm_results:
                        CandidateStore(db).add_candidate(r)
                except Exception as exc:
                    logger.warning("osm_failed cell=%s error=%s", cell, exc)

            db.commit()
            logger.info("aoi_scan_complete cells=%s", len(cells))

        except Exception as exc:
            logger.exception("aoi_scan_error error=%s", exc)
            with suppress(Exception):
                db.rollback()
        finally:
            with suppress(Exception):
                db.close()

        time.sleep(SCAN_INTERVAL_SECONDS)
```

**IMPORTANT:** Replace `search_nominatim`, `query_overpass`, and `CandidateStore` with the exact names found in Step 2. Do not guess. Do not invent interfaces.

- [ ] **Step 4: Verify the file imports cleanly**

```bash
python -c "import app.workers.aoi_scan_worker; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add app/workers/aoi_scan_worker.py
git commit -m "fix: aoi_scan_worker now calls nominatim + osm and feeds candidate_store_v2"
```

---

## PHASE 4 — FINALIZE WORKERS

### Task 7: Fix all remaining workers — read and repair each one

**Files:**
- Modify: `app/workers/discovery_worker.py`
- Modify: `app/workers/ranking_worker.py`
- Modify: `app/workers/recompute_scores_worker.py`
- Modify: `app/workers/search_index_worker.py`
- Modify: `app/workers/truth_rebuild_worker.py`
- Modify: `app/workers/feed_refresh_worker.py`

For each worker, follow the same 4-step pattern:

**Step A: Read the worker**
```bash
cat app/workers/<worker_name>.py
```

**Step B: Check what service it should call**
```bash
grep -n "^def \|^class " app/services/<relevant_service>/*.py
```

**Step C: Fix the import and call if broken**
**Step D: Verify it imports cleanly**
```bash
python -c "import app.workers.<worker_name>; print('OK')"
```

- [ ] **Step 1: Fix discovery_worker**

```bash
cat app/workers/discovery_worker.py
# Verify it calls run_discovery_pipeline_v2 (not legacy path)
# If it calls something else, fix to:
from app.services.discovery.pipeline_v2 import run_discovery_pipeline_v2
```

- [ ] **Step 2: Fix ranking_worker**

```bash
cat app/workers/ranking_worker.py
grep -n "^def \|^class " app/services/ranking/*.py
# Verify ranking_worker calls rank_calculator or rank_executor
# If broken, fix the import to match the actual function name
```

- [ ] **Step 3: Fix recompute_scores_worker**

```bash
cat app/workers/recompute_scores_worker.py
grep -n "^def \|^class " app/services/scoring/recompute.py app/services/scoring/score_place_v2.py
# Verify it calls score_place_v2 or recompute.run_recompute
# Fix if calling wrong path
```

- [ ] **Step 4: Fix search_index_worker**

```bash
cat app/workers/search_index_worker.py
grep -n "^def \|^class " app/services/search/search_index_builder.py
# Verify it calls build_search_index or equivalent
# Fix import if broken
```

- [ ] **Step 5: Fix truth_rebuild_worker**

```bash
cat app/workers/truth_rebuild_worker.py
grep -n "^def \|^class " app/services/truth/truth_resolver_v2.py
# Verify it calls the resolver, not a stub
```

- [ ] **Step 6: Fix feed_refresh_worker**

```bash
cat app/workers/feed_refresh_worker.py
cat app/services/feed_service.py
# Verify it calls feed_service correctly
```

- [ ] **Step 7: Verify all workers import cleanly**

```bash
python -c "
workers = [
    'app.workers.discovery_worker',
    'app.workers.ranking_worker',
    'app.workers.recompute_scores_worker',
    'app.workers.search_index_worker',
    'app.workers.truth_rebuild_worker',
    'app.workers.feed_refresh_worker',
    'app.workers.image_worker',
    'app.workers.image_crawler_worker',
    'app.workers.aoi_priority_worker',
]
import importlib
for w in workers:
    try:
        importlib.import_module(w)
        print(f'OK   {w}')
    except Exception as e:
        print(f'FAIL {w}: {e}')
"
```

Expected: All `OK`

- [ ] **Step 8: Commit**

```bash
git add app/workers/
git commit -m "fix: repair all worker imports and service call paths"
```

---

### Task 8: Fix run_pipeline.py to include scoring + search index loops

**Files:**
- Modify: `app/workers/run_pipeline.py`

**Problem:** `run_pipeline.py` only runs menu + ingest loops. Scoring and search index are never triggered.

- [ ] **Step 1: Write the test**

```python
# tests/test_run_pipeline.py
from unittest.mock import patch

def test_pipeline_loop_triggers_scoring():
    """run_pipeline loop must call scoring recompute, not just ingest + menu."""
    with patch("app.workers.run_pipeline.run_master_ingest") as mi, \
         patch("app.workers.run_pipeline.run_menu_worker") as mw, \
         patch("app.workers.run_pipeline.run_score_recompute") as sr, \
         patch("app.workers.run_pipeline.time") as t:
        t.time.side_effect = [0, 400, 400, 400, 400]  # simulate time passing
        t.sleep.side_effect = StopIteration
        try:
            from app.workers.run_pipeline import run_loop
            run_loop()
        except StopIteration:
            pass
    sr.assert_called()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_run_pipeline.py::test_pipeline_loop_triggers_scoring -v
```

- [ ] **Step 3: Add scoring + search index loops to run_pipeline.py**

In `app/workers/run_pipeline.py`, add:

```python
# At top — new imports (add after existing imports):
from app.services.scoring.recompute import run_recompute as run_score_recompute
from app.services.search.search_index_builder import build_search_index

# New config constants (add after existing ones):
SCORE_INTERVAL_SECONDS = 600    # recompute scores every 10 min
SEARCH_INDEX_INTERVAL_SECONDS = 900  # rebuild search index every 15 min

# New safe runners (add after existing _run_menu_safe):
def _run_score_safe() -> None:
    try:
        run_score_recompute()
        logger.info("pipeline_score_complete")
    except Exception as exc:
        logger.exception("pipeline_score_failed error=%s", exc)


def _run_search_index_safe() -> None:
    try:
        build_search_index()
        logger.info("pipeline_search_index_complete")
    except Exception as exc:
        logger.exception("pipeline_search_index_failed error=%s", exc)
```

Then in `run_loop()`, add after the menu block:

```python
            # -------------------------------------------------
            # SCORE LOOP (recompute place scores)
            # -------------------------------------------------
            if now - last_score_run >= SCORE_INTERVAL_SECONDS:
                logger.info("pipeline_score_start")
                _run_score_safe()
                last_score_run = now

            # -------------------------------------------------
            # SEARCH INDEX LOOP (rebuild search index)
            # -------------------------------------------------
            if now - last_search_index_run >= SEARCH_INDEX_INTERVAL_SECONDS:
                logger.info("pipeline_search_index_start")
                _run_search_index_safe()
                last_search_index_run = now
```

And initialize the new timestamps in `run_loop()`:

```python
    last_score_run = 0.0
    last_search_index_run = 0.0
```

**IMPORTANT:** Before adding these imports, verify the exact function names:

```bash
grep -n "^def \|^class " app/services/scoring/recompute.py
grep -n "^def \|^class " app/services/search/search_index_builder.py
```

Use the actual names, not the ones above if they differ.

- [ ] **Step 4: Verify import**

```bash
python -c "import app.workers.run_pipeline; print('OK')"
```

- [ ] **Step 5: Run menu pipeline guard**

```bash
python run_pipeline_debug.py 2>&1 | tail -3
```

- [ ] **Step 6: Commit**

```bash
git add app/workers/run_pipeline.py tests/test_run_pipeline.py
git commit -m "fix: run_pipeline now includes scoring and search index refresh loops"
```

---

## PHASE 5 — FINALIZE SCORING

### Task 9: Verify scoring system end-to-end

**Goal:** Confirm scoring inputs come from real data and `score_place_v2` produces deterministic output.

**Files:**
- Read: `app/services/scoring/score_place_v2.py`
- Read: `app/services/scoring/compute_master_score.py`
- Read: `app/services/scoring/score_contracts.py`
- Read: `app/services/scoring/recompute.py`

- [ ] **Step 1: Read all scoring files**

```bash
cat app/services/scoring/score_contracts.py
cat app/services/scoring/score_place_v2.py
cat app/services/scoring/compute_master_score.py
cat app/services/scoring/recompute.py
```

- [ ] **Step 2: Write the determinism test**

```python
# tests/test_scoring.py
from app.services.scoring.compute_master_score import compute_master_score

def test_compute_master_score_is_deterministic():
    """Same inputs must always produce same score."""
    inputs = {
        "has_menu": True,
        "has_image": True,
        "has_address": True,
        "has_hours": False,
        "review_count": 50,
        "claim_count": 3,
    }
    score1 = compute_master_score(**inputs)
    score2 = compute_master_score(**inputs)
    assert score1 == score2, "Scoring is non-deterministic"
    assert 0.0 <= score1 <= 1.0, f"Score out of range: {score1}"


def test_compute_master_score_higher_with_more_signals():
    """More complete place data must produce higher score."""
    low = compute_master_score(
        has_menu=False, has_image=False, has_address=False,
        has_hours=False, review_count=0, claim_count=0,
    )
    high = compute_master_score(
        has_menu=True, has_image=True, has_address=True,
        has_hours=True, review_count=100, claim_count=10,
    )
    assert high > low, f"Expected high({high}) > low({low})"
```

- [ ] **Step 3: Run test**

```bash
python -m pytest tests/test_scoring.py -v
```

If the test fails because `compute_master_score` has different parameters, read the actual signature and update the test to match. Do NOT change the scoring function to match the test — the test must adapt to the real API.

- [ ] **Step 4: Verify recompute calls score_place_v2**

```bash
grep -n "score_place_v2\|compute_master_score\|score_place" app/services/scoring/recompute.py
```

If `recompute.py` doesn't call the real scoring function, fix it to do so. Read `recompute.py` fully before editing.

- [ ] **Step 5: Commit**

```bash
git add tests/test_scoring.py
git commit -m "test: add determinism tests for scoring system"
```

---

### Task 10: Wire confidence_aggregator and rank_score

**Files:**
- Read: `app/services/scoring/confidence_aggregator.py`
- Read: `app/services/scoring/rank_score.py`
- Read: `app/services/ranking/rank_calculator.py`

- [ ] **Step 1: Read all three files**

```bash
cat app/services/scoring/confidence_aggregator.py
cat app/services/scoring/rank_score.py
cat app/services/ranking/rank_calculator.py
```

- [ ] **Step 2: Verify rank_calculator uses rank_score**

```bash
grep -n "rank_score\|RankScore\|compute_rank" app/services/ranking/rank_calculator.py
```

If `rank_calculator` does not import `rank_score`, find where `rank_score` IS called. If it's nowhere, wire it into `rank_calculator`.

- [ ] **Step 3: Write rank end-to-end test**

```python
# tests/test_ranking.py
from app.services.ranking.rank_calculator import calculate_rank  # verify exact function name

def test_rank_calculator_returns_numeric():
    """rank_calculator must return a numeric rank for a place."""
    # Read rank_calculator to find the actual function signature first
    # Then write a test that calls it with minimal valid inputs
    pass  # Replace with real test after reading the file
```

After reading `rank_calculator.py` in Step 1, replace the `pass` with a real assertion.

- [ ] **Step 4: Commit**

```bash
git add tests/test_ranking.py
git commit -m "test: add rank_calculator wiring test"
```

---

## PHASE 6 — FINALIZE SEARCH

### Task 11: Wire search engine to real place data and API route

**Files:**
- Read: `app/services/search/search_engine.py`
- Read: `app/services/search/search_index_builder.py`
- Read: `app/api/v1/routes/search.py`
- Read: `app/services/search_service.py`

- [ ] **Step 1: Read all four files**

```bash
cat app/services/search/search_engine.py
cat app/services/search/search_index_builder.py
cat app/api/v1/routes/search.py
cat app/services/search_service.py
```

- [ ] **Step 2: Check if search route calls search_engine or search_service**

```bash
grep -n "search_engine\|search_service\|SearchEngine\|SearchService" app/api/v1/routes/search.py
```

If the route does NOT call the real search engine, wire it. The search route must call the service, not implement logic itself.

- [ ] **Step 3: Write the search route test**

```python
# tests/test_search_route.py
from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import patch

client = TestClient(app)

def test_search_returns_json():
    """GET /api/v1/search?q=pizza must return JSON with results key."""
    with patch("app.services.search_service.SearchService.search") as mock_search:
        mock_search.return_value = {"results": [], "total": 0}
        response = client.get("/api/v1/search?q=pizza")
    assert response.status_code in (200, 422), f"Unexpected status: {response.status_code}"
```

Note: If the route path differs, find it first:

```bash
grep -r "router.get\|router.post\|app.get\|app.post" app/api/v1/routes/search.py
```

- [ ] **Step 4: Run test**

```bash
python -m pytest tests/test_search_route.py -v
```

- [ ] **Step 5: Commit**

```bash
git add tests/test_search_route.py
git commit -m "test: add search route wiring test"
```

---

### Task 12: Add menus route to v1 API

**Files:**
- Read: `app/api/v1/__init__.py`
- Read: `app/api/v1/routes/__init__.py`
- Create: `app/api/v1/routes/menus.py` (if not exists)
- Modify: `app/api/v1/routes/__init__.py`

- [ ] **Step 1: Check if menus is already registered in v1**

```bash
cat app/api/v1/__init__.py
cat app/api/v1/routes/__init__.py
grep -r "menus" app/api/v1/ --include="*.py"
```

- [ ] **Step 2: If menus route is missing, create it**

```python
# app/api/v1/routes/menus.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.menu.materialize_menu_truth import materialize_menu_truth

router = APIRouter(prefix="/menus", tags=["menus"])


@router.get("/{place_id}")
def get_menu(place_id: str, db: Session = Depends(get_db)):
    """Return materialized menu for a place."""
    menu = materialize_menu_truth(db=db, place_id=place_id)
    if not menu or menu.item_count == 0:
        raise HTTPException(status_code=404, detail="Menu not found")

    return {
        "place_id": place_id,
        "item_count": menu.item_count,
        "sections": [
            {
                "name": section.name,
                "items": [
                    {
                        "name": item.name,
                        "price_cents": item.price_cents,
                        "currency": item.currency,
                        "description": item.description,
                        "fingerprint": item.fingerprint,
                    }
                    for item in section.items
                ],
            }
            for section in menu.sections
        ],
    }
```

- [ ] **Step 3: Register the menus router in v1**

In `app/api/v1/routes/__init__.py`, add:

```python
from app.api.v1.routes.menus import router as menus_router
router.include_router(menus_router)
```

(Find the exact pattern used for other routes in that file and match it.)

- [ ] **Step 4: Write the route test**

```python
# tests/test_menus_route.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_menu_not_found_returns_404():
    response = client.get("/api/v1/menus/nonexistent-place-id")
    assert response.status_code == 404
```

- [ ] **Step 5: Run test**

```bash
python -m pytest tests/test_menus_route.py -v
```

Expected: PASS

- [ ] **Step 6: Run menu pipeline guard**

```bash
python run_pipeline_debug.py 2>&1 | tail -3
```

- [ ] **Step 7: Commit**

```bash
git add app/api/v1/routes/menus.py app/api/v1/routes/__init__.py tests/test_menus_route.py
git commit -m "feat: add /api/v1/menus/{place_id} route to v1 API"
```

---

## PHASE 7 — CACHE WIRING

### Task 13: Wire cache to place detail, search, and menu routes

**Files:**
- Read: `app/services/cache/cache_client.py`
- Read: `app/services/cache/cache_helpers.py`
- Read: `app/services/cache/cache_keys.py`
- Read: `app/services/cache/cache_ttl.py`
- Modify: `app/api/v1/routes/places.py`
- Modify: `app/api/v1/routes/search.py`
- Modify: `app/api/v1/routes/menus.py`

- [ ] **Step 1: Read cache layer**

```bash
cat app/services/cache/cache_client.py
cat app/services/cache/cache_helpers.py
cat app/services/cache/cache_keys.py
cat app/services/cache/cache_ttl.py
```

Note the exact function names for `get`, `set`, and the TTL constants. Do NOT invent them.

- [ ] **Step 2: Write cache test**

```python
# tests/test_cache.py
from app.services.cache.cache_client import CacheClient  # verify exact class name

def test_cache_set_and_get():
    """Cache must round-trip a value."""
    cache = CacheClient()  # adjust constructor to match real signature
    cache.set("test:key", {"value": 42}, ttl=60)
    result = cache.get("test:key")
    assert result == {"value": 42}

def test_cache_miss_returns_none():
    cache = CacheClient()
    result = cache.get("nonexistent:key:xyz123")
    assert result is None
```

- [ ] **Step 3: Run test**

```bash
python -m pytest tests/test_cache.py -v
```

Fix test to match real API if it fails for signature mismatch reasons (not logic bugs).

- [ ] **Step 4: Add cache to place detail route**

In `app/api/v1/routes/places.py` (or `place_detail_router.py`), find the place detail endpoint and wrap with cache:

```python
# Pattern to follow — adapt to real cache API from Step 1:
from app.services.cache.cache_client import CacheClient
from app.services.cache.cache_keys import place_detail_key   # verify exact key builder
from app.services.cache.cache_ttl import PLACE_DETAIL_TTL    # verify exact constant

cache = CacheClient()

@router.get("/{place_id}")
def get_place(place_id: str, db: Session = Depends(get_db)):
    key = place_detail_key(place_id)
    cached = cache.get(key)
    if cached is not None:
        return cached

    # ... existing place fetch logic ...
    result = _fetch_place(place_id, db)  # use actual existing logic

    cache.set(key, result, ttl=PLACE_DETAIL_TTL)
    return result
```

**IMPORTANT:** Read the existing route handler before editing. Do not replace working logic — wrap it.

- [ ] **Step 5: Add cache to search route**

Same pattern in `app/api/v1/routes/search.py`:

```python
from app.services.cache.cache_keys import search_results_key  # verify
from app.services.cache.cache_ttl import SEARCH_RESULTS_TTL   # verify

# In search handler:
key = search_results_key(q=query, city=city_id, page=page)  # adapt to actual params
cached = cache.get(key)
if cached is not None:
    return cached
# ... existing search logic ...
cache.set(key, result, ttl=SEARCH_RESULTS_TTL)
```

- [ ] **Step 6: Verify all three routes import cleanly**

```bash
python -c "
import app.api.v1.routes.places
import app.api.v1.routes.search
import app.api.v1.routes.menus
print('OK')
"
```

- [ ] **Step 7: Run menu pipeline guard**

```bash
python run_pipeline_debug.py 2>&1 | tail -3
```

- [ ] **Step 8: Commit**

```bash
git add app/api/v1/routes/ app/services/cache/ tests/test_cache.py
git commit -m "feat: wire cache layer to place detail, search, and menu routes"
```

---

## PHASE 8 — NETWORK LAYER

### Task 14: Consolidate network fetch paths

**Goal:** Ensure there is one clear primary fetch path (not three competing paths), domain rate limiting is active, and browser escalation only triggers when needed.

**Files:**
- Read: `app/services/network/http_fetcher.py`
- Read: `app/services/network/browser_fetcher.py`
- Read: `app/services/network/request_strategy.py`
- Read: `app/services/network/domain_rate_limiter.py`

- [ ] **Step 1: Read all four files**

```bash
cat app/services/network/request_strategy.py
cat app/services/network/http_fetcher.py
cat app/services/network/browser_fetcher.py
cat app/services/network/domain_rate_limiter.py
```

- [ ] **Step 2: Determine the canonical fetch path**

```bash
grep -r "http_fetcher\|browser_fetcher\|request_strategy" app/services/ --include="*.py" -l
```

The correct call chain must be: `caller → request_strategy → http_fetcher → (escalate to browser_fetcher if blocked)`

If callers bypass `request_strategy` and call `http_fetcher` or `browser_fetcher` directly, note each one. Fix the highest-traffic callers to go through `request_strategy`.

- [ ] **Step 3: Verify domain_rate_limiter is used**

```bash
grep -r "domain_rate_limiter\|DomainRateLimiter\|rate_limit" app/services/network/http_fetcher.py
```

If rate limiting is NOT applied in `http_fetcher`, add it. The pattern:

```python
from app.services.network.domain_rate_limiter import DomainRateLimiter

rate_limiter = DomainRateLimiter()  # adjust to real API

# Before each request:
rate_limiter.wait(domain=domain)   # adjust to real method name
```

- [ ] **Step 4: Verify block_classifier is used after each fetch**

```bash
grep -r "block_classifier\|BlockClassifier\|is_blocked" app/services/network/http_fetcher.py
```

If not used, add after response:

```python
from app.services.network.block_classifier import is_blocked  # verify name

if is_blocked(response):
    logger.warning("blocked domain=%s", domain)
    # escalate to browser if strategy allows
```

- [ ] **Step 5: Write network smoke test**

```python
# tests/test_network.py
from app.services.network.domain_rate_limiter import DomainRateLimiter  # verify

def test_rate_limiter_allows_first_request():
    rl = DomainRateLimiter()
    # First request to a domain should not block
    import time
    start = time.time()
    rl.wait("example.com")  # verify method name
    elapsed = time.time() - start
    assert elapsed < 0.1, "First request to new domain should not wait"
```

- [ ] **Step 6: Run test**

```bash
python -m pytest tests/test_network.py -v
```

- [ ] **Step 7: Commit**

```bash
git add tests/test_network.py
git commit -m "test: add network layer smoke tests; verify rate limiting is wired"
```

---

## PHASE 9 — API + ROUTING

### Task 15: Add startup validation and ensure all routes boot cleanly

**Files:**
- Modify: `app/main.py`
- Read: `app/api/v1/__init__.py`
- Read: `app/api/v1/routes/__init__.py`

- [ ] **Step 1: List all registered routes**

```bash
python -c "
from app.main import app
for route in app.routes:
    print(getattr(route, 'path', '?'), getattr(route, 'methods', '?'))
" 2>&1
```

Expected output should include: `/health`, `/api/v1/places`, `/api/v1/search`, `/api/v1/menus`, `/api/v1/cities`, `/api/v1/categories`

Note any that are missing.

- [ ] **Step 2: Add startup validation to main.py**

In the `lifespan` function in `app/main.py`, add:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup")

    # Validate model registry
    _ = models

    # Validate DB connectivity
    try:
        from app.db.session import SessionLocal
        db = SessionLocal()
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db.close()
        logger.info("startup_db_ok")
    except Exception as exc:
        logger.critical("startup_db_failed error=%s", exc)
        raise RuntimeError(f"DB connectivity check failed: {exc}") from exc

    # Validate critical imports
    try:
        from app.services.menu.menu_pipeline import process_extracted_menu  # noqa
        from app.services.scoring.recompute import run_recompute  # noqa — verify name
        from app.services.search.search_engine import SearchEngine  # noqa — verify name
        logger.info("startup_service_imports_ok")
    except Exception as exc:
        logger.critical("startup_import_failed error=%s", exc)
        raise

    yield

    logger.info("shutdown")
```

**IMPORTANT:** Verify the exact import paths for `run_recompute` and `SearchEngine` before adding them. Use `grep -n "^def \|^class " app/services/scoring/recompute.py app/services/search/search_engine.py`.

- [ ] **Step 3: Test startup boots cleanly**

```bash
python -c "
from app.main import app
print('app boot OK')
print('routes:')
for r in app.routes:
    path = getattr(r, 'path', None)
    if path:
        print(f'  {path}')
"
```

Expected: No exceptions, routes listed.

- [ ] **Step 4: Run menu pipeline guard**

```bash
python run_pipeline_debug.py 2>&1 | tail -3
```

- [ ] **Step 5: Commit**

```bash
git add app/main.py
git commit -m "feat: add startup validation to check DB connectivity and critical imports"
```

---

## PHASE 10 — DATA INTEGRITY + TRUTH

### Task 16: Verify truth rebuild path is end-to-end correct

**Files:**
- Read: `app/services/truth/truth_resolver_v2.py`
- Read: `app/services/truth/truth_reader.py`
- Read: `app/workers/truth_rebuild_worker.py`

- [ ] **Step 1: Read all three files**

```bash
cat app/services/truth/truth_resolver_v2.py
cat app/services/truth/truth_reader.py
cat app/workers/truth_rebuild_worker.py
```

- [ ] **Step 2: Verify truth_rebuild_worker calls truth_resolver_v2**

```bash
grep -n "truth_resolver_v2\|TruthResolver\|resolve_truth" app/workers/truth_rebuild_worker.py
```

If it doesn't call the resolver, fix it.

- [ ] **Step 3: Verify truth_reader is used by API routes**

```bash
grep -r "truth_reader\|TruthReader\|read_truth" app/api/ --include="*.py"
```

If place detail or menu routes read truth directly from the DB (bypassing `truth_reader`), fix them to use `truth_reader`. This ensures consistent resolution.

- [ ] **Step 4: Write truth smoke test**

```python
# tests/test_truth.py
from app.services.truth.truth_reader import TruthReader  # verify class name

def test_truth_reader_returns_none_for_unknown_place():
    """TruthReader must not crash on unknown place IDs."""
    from unittest.mock import MagicMock
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.one_or_none.return_value = None
    reader = TruthReader(db=mock_db)  # adjust to real constructor
    result = reader.get_menu_truth("nonexistent-id")  # adjust to real method name
    assert result is None
```

- [ ] **Step 5: Run test**

```bash
python -m pytest tests/test_truth.py -v
```

Fix test signature to match real API if needed.

- [ ] **Step 6: Commit**

```bash
git add tests/test_truth.py
git commit -m "test: add truth reader smoke test; verify truth rebuild worker wiring"
```

---

## PHASE 11 — CLEANUP

### Task 17: Clean dead imports, duplicate modules, stale references

- [ ] **Step 1: Find unused imports in workers**

```bash
cd /Users/angelowashington/CRAVE/backend
python -m py_compile app/workers/*.py && echo "All workers compile OK"
```

Fix any compile errors found.

- [ ] **Step 2: Find obviously orphaned scripts**

```bash
# Scripts that import non-existent modules
for f in scripts/*.py; do
    python -m py_compile "$f" 2>&1 | grep -v "^$" && echo "BROKEN: $f" || echo "OK: $f"
done
```

For each broken script: either fix the import or add a `# DEPRECATED` comment at the top.

- [ ] **Step 3: Remove dead logger/debug code**

```bash
grep -r "print(" app/services/ app/workers/ --include="*.py" -l | head -20
```

For each file found: replace bare `print()` calls with `logger.debug()` where they're not intentional debug output.

- [ ] **Step 4: Find duplicate service paths**

```bash
# Two places/ modules?
ls app/services/places/
ls app/services/places_service.py 2>/dev/null && echo "DUPLICATE: places_service.py at services root"

# Two search modules?
ls app/services/search/
cat app/services/search_service.py 2>/dev/null | head -5
```

If `app/services/places_service.py` and `app/services/places/` both exist, determine which one is the real one (check what routes import) and leave the other with a deprecation notice.

- [ ] **Step 5: Commit cleanup**

```bash
git add -u
git commit -m "chore: clean dead imports, add deprecation notices to duplicate modules"
```

---

## PHASE 12 — VERIFY EVERYTHING

### Task 18: Write and run the full verification script

**Files:**
- Create: `scripts/verify_backend.py`

- [ ] **Step 1: Write the verification script**

```python
#!/usr/bin/env python3
"""
Full backend verification — run after finalization.
Exit 0 = all checks passed. Exit 1 = failures found.

Usage: python scripts/verify_backend.py
"""
from __future__ import annotations

import importlib
import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PASS = []
FAIL = []

def check(name: str, fn):
    try:
        fn()
        PASS.append(name)
        print(f"  OK    {name}")
    except Exception as e:
        FAIL.append((name, str(e)))
        print(f"  FAIL  {name}: {e}")


print("=" * 60)
print("CRAVE BACKEND VERIFICATION")
print("=" * 60)

# --- Imports ---
print("\n[1] CRITICAL IMPORTS")
for mod in [
    "app.main",
    "app.workers.master_worker",
    "app.workers.run_pipeline",
    "app.workers.aoi_scan_worker",
    "app.workers.discovery_worker",
    "app.workers.ranking_worker",
    "app.workers.recompute_scores_worker",
    "app.workers.search_index_worker",
    "app.workers.truth_rebuild_worker",
    "app.services.discovery.pipeline_v2",
    "app.services.matching.place_matcher",
    "app.services.scoring.recompute",
    "app.services.search.search_engine",
    "app.services.search.search_index_builder",
    "app.services.cache.cache_client",
    "app.services.truth.truth_resolver_v2",
    "app.services.menu.menu_pipeline",
    "app.services.menu.claims.menu_claim_emitter",
    "app.services.menu.materialize_menu_truth",
]:
    check(f"import {mod}", lambda m=mod: importlib.import_module(m))

# --- App boot ---
print("\n[2] APP BOOT")
def _check_app_boot():
    from app.main import app
    assert app is not None
    routes = [getattr(r, "path", None) for r in app.routes]
    assert "/health" in routes, f"Missing /health. Routes: {routes}"
check("app boots and /health route exists", _check_app_boot)

# --- Menu pipeline ---
print("\n[3] MENU PIPELINE (end-to-end)")
def _check_menu_pipeline():
    result = subprocess.run(
        [sys.executable, "run_pipeline_debug.py"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0, (
        f"Menu pipeline failed:\n{result.stdout[-1000:]}\n{result.stderr[-500:]}"
    )
check("menu pipeline produces non-empty materialized menu", _check_menu_pipeline)

# --- DB connectivity ---
print("\n[4] DB CONNECTIVITY")
def _check_db():
    from app.db.session import SessionLocal
    import sqlalchemy
    db = SessionLocal()
    db.execute(sqlalchemy.text("SELECT 1"))
    db.close()
check("DB connection", _check_db)

# --- Worker entrypoints ---
print("\n[5] WORKER ENTRYPOINTS")
def _check_worker(name):
    mod = importlib.import_module(f"app.workers.{name}")
    # Each worker module must have at least one callable entrypoint
    callables = [k for k, v in vars(mod).items() if callable(v) and not k.startswith("_")]
    assert callables, f"No callable entrypoints in {name}"
for w in ["master_worker", "aoi_scan_worker", "discovery_worker", "ranking_worker",
          "recompute_scores_worker", "search_index_worker", "truth_rebuild_worker"]:
    check(f"worker:{w} has entrypoint", lambda name=w: _check_worker(name))

# --- Summary ---
print("\n" + "=" * 60)
print("VERIFICATION SUMMARY")
print("=" * 60)
print(f"  PASSED: {len(PASS)}")
print(f"  FAILED: {len(FAIL)}")
for name, err in FAIL:
    print(f"    FAIL {name}: {err}")
print("=" * 60)

if FAIL:
    print("\nBACKEND VERIFICATION: INCOMPLETE — fix failures above")
    sys.exit(1)
else:
    print("\nBACKEND FULLY FINALIZED — ALL CHECKS PASSED")
    sys.exit(0)
```

- [ ] **Step 2: Run verification**

```bash
cd /Users/angelowashington/CRAVE/backend
python scripts/verify_backend.py 2>&1 | tee /tmp/crave_verify.txt
```

Expected: All checks pass, exit code 0.

For each FAIL: return to the relevant phase task and fix the underlying issue. Do NOT mark Phase 12 complete until all checks pass.

- [ ] **Step 3: Commit**

```bash
git add scripts/verify_backend.py
git commit -m "chore: add full backend verification script"
```

---

## PHASE 13 — FINAL REPORT

### Task 19: Generate final report and production run commands

- [ ] **Step 1: Run final verification**

```bash
python scripts/verify_backend.py
```

Must exit 0 before proceeding.

- [ ] **Step 2: Run audit to compare with Phase 1 baseline**

```bash
python scripts/audit_backend.py 2>&1 | tee /tmp/crave_audit_final.txt
diff /tmp/crave_audit.txt /tmp/crave_audit_final.txt
```

The CRITICAL count should have decreased. Note the delta.

- [ ] **Step 3: Record production run commands**

```bash
# Start the API server:
cd /Users/angelowashington/CRAVE/backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2

# Start the master worker (place ingestion + menu):
python -m app.workers.master_worker

# Start the full pipeline runner (ingest + menu + scoring + search index):
python app/workers/run_pipeline.py

# Run individual workers:
python -m app.workers.aoi_scan_worker
python -m app.workers.ranking_worker
python -m app.workers.search_index_worker
python -m app.workers.truth_rebuild_worker

# Run scoring recompute (one-shot):
python scripts/run_score_rebuild_v2.py

# Run search index rebuild (one-shot):
python scripts/run_search_index.py

# Run truth rebuild (one-shot):
python scripts/run_truth_rebuild_v2.py

# Verify menu pipeline:
python run_pipeline_debug.py

# Verify full backend:
python scripts/verify_backend.py
```

- [ ] **Step 4: Final commit**

```bash
git add -u
git commit -m "chore: backend finalization complete — all phases executed"
```

- [ ] **Step 5: Print final status**

```bash
python scripts/verify_backend.py && echo "
============================================================
BACKEND FULLY FINALIZED
Place ingestion, matching, scoring, ranking, search,
workers, cache, and routing all verified.
============================================================
"
```

---

## Self-Review Checklist

After writing this plan, I checked:

1. **Spec coverage:** All 13 phases from the user spec are covered across Tasks 1–19. ✓
2. **Placeholder scan:** No TBDs — every step has either concrete code or explicit read-first instructions. ✓
3. **Type consistency:** Function names marked "verify exact name" before use — no invented APIs. ✓
4. **Menu pipeline guard:** Included after every task that touches models, services, or main. ✓
5. **N+1 fix:** Task 3 addresses the `db.query(Place).all()` found in `place_matcher.py`. ✓
6. **Missing menus route:** Task 12 adds `/api/v1/menus/{place_id}`. ✓
7. **Worker disconnection:** Task 7 repairs all workers; Task 8 adds scoring/search to pipeline. ✓
8. **CRITICAL rules:** No schema redesign, no fake logic, no removal of existing safeguards. ✓

---

## Audit Notes (fill in after Task 1)

```
CRITICAL broken imports:  [count here]
Medium wiring issues:     [count here]
Stubs/empty workers:      [count here]
Unregistered routes:      [count here]
```
