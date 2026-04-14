# CRAVE Backend Phase 3 — Audit, Fix, Validate, Lock

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Perform a full system audit of the CRAVE backend, fix every proven bug and gap, validate end-to-end paths, and produce a production-readiness verdict.

**Architecture:** Audit-first — read code, measure real behavior, then fix only what is proven broken. All fixes must keep `python run_pipeline_debug.py` green. No placeholder logic, no reckless deletion.

**Tech Stack:** Python 3.x, FastAPI, SQLAlchemy 2.x, SQLite (dev), in-memory ResponseCache, custom worker loops.

**Pipeline guard:** `python run_pipeline_debug.py` — must pass at every checkpoint.

---

## CONFIRMED BUGS (pre-audit findings from codebase read)

| # | File | Issue | Severity |
|---|------|-------|----------|
| 1 | `app/workers/run_pipeline.py` | Imports `run_master_ingest` from `app.services.ingest.master_ingest` — **fails on import** (broken transitive import chain) | CRITICAL |
| 2 | `app/api/v1/routes/search.py` | Calls `search_places` directly — **bypasses `search_engine.py` and `search_ranker.py` entirely**; Phase 1 ranking improvements are dead code | HIGH |
| 3 | `app/api/v1/routes/places.py` | No try/except around `query_list_places()` — any DB error returns unhandled 500 | MEDIUM |
| 4 | `app/workers/ranking_worker.py` | `run_worker()` has no error-count guard — one systemic failure kills the worker permanently | MEDIUM |
| 5 | `app/services/scoring/score_all_places_v2.py` | Queries `needs_recompute=True` but nothing in active pipeline sets that flag — **always returns 0 attempted** | MEDIUM |
| 6 | `app/services/cache/cache_helpers.py` | **Empty file** — referenced in imports chain, provides no utility | LOW |
| 7 | `app/workers/recompute_scores_worker.py` | Queue dir `var/queue/` may not exist — crashes on first write | LOW |
| 8 | Scoring | `score_place_v2` writes 0–100 scale; `recompute.py` writes raw ~0–3 float to same DB fields — **incompatible if both ever run** | HIGH |

---

## Files Modified / Created

| File | Action | Reason |
|------|--------|--------|
| `app/workers/run_pipeline.py` | Rewrite | Fix broken import — redirect to master_worker or deprecate |
| `app/api/v1/routes/search.py` | Modify | Wire to `execute_search()` from `search_engine.py` |
| `app/api/v1/routes/places.py` | Modify | Add try/except guard |
| `app/workers/ranking_worker.py` | Modify | Add MAX_ERRORS guard |
| `app/services/cache/cache_helpers.py` | Implement | Add real utility functions |
| `app/workers/recompute_scores_worker.py` | Modify | Ensure queue dir exists |
| `app/services/scoring/score_all_places_v2.py` | Document | Mark as inactive path, add warning comment |
| `scripts/run_phase3_audit.py` | Create | End-to-end audit + metrics script |

---

## Task 1: Fix `run_pipeline.py` — Broken Import (CRITICAL)

**Files:**
- Modify: `app/workers/run_pipeline.py`

- [ ] **Step 1: Confirm the breakage**

```bash
python -c "from app.workers.run_pipeline import run_loop" 2>&1 | head -10
```

Expected: ImportError chain ending at `extract_menu_from_url` or similar.

- [ ] **Step 2: Rewrite run_pipeline.py to redirect to master_worker**

The file's purpose (run discovery + menu in a loop) is fully superseded by `master_worker.py`. Replace the broken import with a clean redirect:

```python
from __future__ import annotations

"""
DEPRECATED: run_pipeline.py

This file previously ran a dual-loop pipeline (discovery + menu).
That logic is now fully handled by master_worker.py.

Run instead:
    python app/workers/run_master_worker.py

This file is kept as a compatibility shim and will not break on import.
"""

import logging

logger = logging.getLogger(__name__)


def run_loop() -> None:
    """Redirect to master_worker. Kept for backward compatibility."""
    logger.warning(
        "run_pipeline.run_loop() is deprecated — use run_master_worker.py instead"
    )
    from app.workers.master_worker import run_master_worker
    run_master_worker()


if __name__ == "__main__":
    run_loop()
```

- [ ] **Step 3: Verify import is clean**

```bash
python -c "from app.workers.run_pipeline import run_loop; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Run pipeline guard**

```bash
python run_pipeline_debug.py 2>&1 | tail -3
```

Expected: `PIPELINE COMPLETE — NON-EMPTY MENU MATERIALIZED`

---

## Task 2: Wire Search Route to `search_engine.py` (HIGH)

**Files:**
- Modify: `app/api/v1/routes/search.py`

- [ ] **Step 1: Confirm current search route bypasses search_engine**

```bash
python -c "
import ast, sys
src = open('app/api/v1/routes/search.py').read()
print('execute_search' in src, 'search_places' in src)
"
```

Expected: `False True` — confirming search_engine is NOT used.

- [ ] **Step 2: Replace `search_places` import with `execute_search`**

Change line 12:
```python
from app.services.query.search_query import search_places
```
To:
```python
from app.services.search.search_engine import execute_search
```

- [ ] **Step 3: Replace the query call**

Change this block:
```python
    try:
        results, total = search_places(
            db=db,
            query=query,
            city_id=city_id,
            category_id=category_id,
            price_tier=price_tier,
            limit=page_size,
            offset=offset,
        )
```

To:
```python
    try:
        results, total = execute_search(
            db,
            query=query,
            city_id=city_id,
            category_id=category_id,
            price_tier=price_tier,
            limit=page_size,
            offset=offset,
        )
```

- [ ] **Step 4: Verify import is clean**

```bash
python -c "from app.api.v1.routes.search import search; print('OK')" 2>&1
```

Expected: `OK` (note: FastAPI not in system Python, so use venv if available; otherwise verify file syntax)

```bash
python -m py_compile app/api/v1/routes/search.py && echo "syntax OK"
```

Expected: `syntax OK`

- [ ] **Step 5: Run pipeline guard**

```bash
python run_pipeline_debug.py 2>&1 | tail -3
```

Expected: `PIPELINE COMPLETE — NON-EMPTY MENU MATERIALIZED`

---

## Task 3: Guard `places.py` Route Against Unhandled Errors (MEDIUM)

**Files:**
- Modify: `app/api/v1/routes/places.py`

- [ ] **Step 1: Add try/except around query and serialization**

Replace the body of `get_places()` after the cache read with:

```python
    cache_key = feed_key(
        city_id=city_id,
        page=page,
        page_size=page_size,
    )

    try:
        cached = response_cache.get(cache_key)
        if cached is not None:
            return cached
    except Exception as exc:
        logger.debug("places_cache_read_failed error=%s", exc)

    offset = (page - 1) * page_size

    try:
        results, total = query_list_places(
            db=db,
            city_id=city_id,
            limit=page_size,
            offset=offset,
        )
    except Exception as exc:
        logger.exception("places_query_failed city_id=%s error=%s", city_id, exc)
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")

    items = []
    for p in results:
        try:
            items.append(PlaceOut.model_validate(p, from_attributes=True))
        except Exception as exc:
            logger.debug("places_serialize_failed place_id=%s error=%s", getattr(p, "id", None), exc)

    response = PlacesResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )

    try:
        response_cache.set(cache_key, response, feed_ttl(city_id=city_id))
    except Exception as exc:
        logger.debug("places_cache_write_failed error=%s", exc)

    return response
```

Also add `import logging` and `logger = logging.getLogger(__name__)` at top if not present.

- [ ] **Step 2: Verify syntax**

```bash
python -m py_compile app/api/v1/routes/places.py && echo "syntax OK"
```

Expected: `syntax OK`

- [ ] **Step 3: Run pipeline guard**

```bash
python run_pipeline_debug.py 2>&1 | tail -3
```

---

## Task 4: Fix `ranking_worker.py` — Add Error Guard (MEDIUM)

**Files:**
- Modify: `app/workers/ranking_worker.py`

- [ ] **Step 1: Add MAX_ERRORS and error counting to `run_worker()`**

Replace `run_worker()`:

```python
MAX_ERRORS = 20


def run_worker(
    *,
    interval_seconds: int = 3600,
) -> None:
    logger.info("ranking_worker_start")
    error_count = 0

    while True:
        db: Session = SessionLocal()
        try:
            run_ranking_cycle(db)
            logger.info("ranking_cycle_complete sleeping=%ss", interval_seconds)
            error_count = 0
        except Exception as exc:
            error_count += 1
            logger.exception("ranking_cycle_failed count=%s error=%s", error_count, exc)
            if error_count >= MAX_ERRORS:
                logger.critical("ranking_worker_stopping — too many errors")
                raise
        finally:
            from contextlib import suppress
            with suppress(Exception):
                db.close()

        time.sleep(interval_seconds)
```

- [ ] **Step 2: Verify import**

```bash
python -c "from app.workers.ranking_worker import run_worker; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Run pipeline guard**

```bash
python run_pipeline_debug.py 2>&1 | tail -3
```

---

## Task 5: Implement `cache_helpers.py` (LOW)

**Files:**
- Implement: `app/services/cache/cache_helpers.py`

- [ ] **Step 1: Write real helper functions**

```python
from __future__ import annotations

from typing import Any, Callable, Optional, TypeVar

from app.services.cache.response_cache import response_cache

T = TypeVar("T")


def get_or_set(
    key: str,
    factory: Callable[[], T],
    ttl_seconds: int = 60,
) -> T:
    """
    Return cached value if present; else call factory(), cache, and return.

    Usage:
        result = get_or_set("my_key", lambda: expensive_query(), ttl_seconds=120)
    """
    cached = response_cache.get(key)
    if cached is not None:
        return cached

    value = factory()
    response_cache.set(key, value, ttl_seconds=ttl_seconds)
    return value


def invalidate(key: str) -> None:
    """Delete a single cache entry."""
    response_cache.delete(key)


def invalidate_place(place_id: str) -> None:
    """Invalidate place detail cache entry."""
    from app.services.cache.cache_keys import place_detail_key
    response_cache.delete(place_detail_key(place_id=place_id))


def invalidate_search(
    *,
    query: str,
    city_id: str,
    category_id: Optional[str] = None,
    price_tier: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
) -> None:
    """Invalidate a specific search cache entry."""
    from app.services.cache.cache_keys import search_cache_key
    key = search_cache_key(
        query=query,
        city_id=city_id,
        category_id=category_id,
        price_tier=price_tier,
        page=page,
        page_size=page_size,
    )
    response_cache.delete(key)
```

- [ ] **Step 2: Verify import**

```bash
python -c "from app.services.cache.cache_helpers import get_or_set, invalidate_place; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Run pipeline guard**

```bash
python run_pipeline_debug.py 2>&1 | tail -3
```

---

## Task 6: Fix `recompute_scores_worker.py` — Queue Dir Creation (LOW)

**Files:**
- Modify: `app/workers/recompute_scores_worker.py`

- [ ] **Step 1: Add directory creation before queue access**

After the `QUEUE_FILE` constant (around line 24), add:

```python
# Ensure queue directory exists on first use
def _ensure_queue_dir() -> None:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 2: Call it at the top of `_read_jobs()`**

At the start of `_read_jobs()`, add:
```python
    _ensure_queue_dir()
```

And at the start of `_truncate_queue()`:
```python
    _ensure_queue_dir()
```

- [ ] **Step 3: Verify import**

```bash
python -c "from app.workers.recompute_scores_worker import worker_once; print('OK')"
```

Expected: `OK`

---

## Task 7: Document Orphaned `score_all_places_v2.py` Path (MEDIUM)

**Files:**
- Modify: `app/services/scoring/score_all_places_v2.py`

- [ ] **Step 1: Add warning docstring and guard**

At the top of `score_all_places_v2()`, add a clear warning comment:

```python
    # ⚠️  IMPORTANT: This function is ONLY triggered when places have
    # `needs_recompute = True`. As of Phase 3, nothing in the active
    # pipeline sets that flag, so this function effectively never runs.
    #
    # The active scoring path is:
    #   recompute_scores_worker.py → recompute.py → recompute_place_scores()
    #
    # score_all_places_v2 produces scores on a 0-100 scale.
    # recompute_place_scores produces raw ~0-3 floats.
    # DO NOT activate both simultaneously — they write to the same DB fields.
    #
    # To activate this path: set needs_recompute=True on Place records
    # and run recompute_scores_worker.py in queue mode.
```

- [ ] **Step 2: Verify no syntax errors**

```bash
python -m py_compile app/services/scoring/score_all_places_v2.py && echo "OK"
```

---

## Task 8: Create `scripts/run_phase3_audit.py` — Full Audit Script

**Files:**
- Create: `scripts/run_phase3_audit.py`

- [ ] **Step 1: Write the full audit + metrics script**

```python
#!/usr/bin/env python3
"""
Phase 3 Full System Audit Script.

Runs all validation checks and prints a complete production-readiness report.

Usage:
    python scripts/run_phase3_audit.py
"""
from __future__ import annotations

import sys
import os
import time
import importlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, func, text
from app.db.session import SessionLocal
from app.db.models.place import Place
from app.db.models.place_claim import PlaceClaim
from app.db.models.place_truth import PlaceTruth
from app.db.models.city import City


PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"

results = []


def check(name, fn):
    try:
        status, detail = fn()
        results.append((name, status, detail))
        symbol = "✓" if status == PASS else ("⚠" if status == WARN else "✗")
        print(f"  {symbol} [{status}] {name}: {detail}")
    except Exception as exc:
        results.append((name, FAIL, str(exc)))
        print(f"  ✗ [FAIL] {name}: EXCEPTION — {exc}")


def _count(db, model, *conditions):
    stmt = select(func.count()).select_from(model)
    for c in conditions:
        stmt = stmt.where(c)
    return db.execute(stmt).scalar_one()


print("\n" + "=" * 70)
print("  CRAVE PHASE 3 SYSTEM AUDIT")
print("=" * 70)

db = SessionLocal()

# ── SECTION 1: IMPORT CHECKS ──────────────────────────────────────────
print("\n[1] IMPORT CHECKS")

def check_run_pipeline():
    import app.workers.run_pipeline
    return PASS, "run_pipeline imports cleanly"
check("run_pipeline import", check_run_pipeline)

def check_master_worker():
    from app.workers.master_worker import run_master_worker
    return PASS, "master_worker imports cleanly"
check("master_worker import", check_master_worker)

def check_search_engine():
    from app.services.search.search_engine import execute_search
    return PASS, "search_engine imports cleanly"
check("search_engine import", check_search_engine)

def check_cache_helpers():
    from app.services.cache.cache_helpers import get_or_set, invalidate_place
    return PASS, "cache_helpers imports cleanly"
check("cache_helpers import", check_cache_helpers)

def check_recompute_worker():
    from app.workers.recompute_scores_worker import worker_once
    return PASS, "recompute_scores_worker imports cleanly"
check("recompute_scores_worker import", check_recompute_worker)

def check_ranking_worker():
    from app.workers.ranking_worker import run_worker
    return PASS, "ranking_worker imports cleanly"
check("ranking_worker import", check_ranking_worker)

def check_search_route():
    import ast
    src = open("app/api/v1/routes/search.py").read()
    if "execute_search" in src:
        return PASS, "search route uses execute_search"
    return FAIL, "search route still uses old search_places — not wired to search_engine.py"
check("search route wired to search_engine", check_search_route)

# ── SECTION 2: DATABASE METRICS ────────────────────────────────────────
print("\n[2] DATABASE METRICS")

total_places = _count(db, Place)
active_places = _count(db, Place, Place.is_active.is_(True))
with_menu = _count(db, Place, Place.has_menu.is_(True))
no_geo = _count(db, Place, Place.is_active.is_(True), Place.lat.is_(None))
no_score = _count(db, Place, Place.is_active.is_(True), Place.master_score.is_(None))
total_claims = _count(db, PlaceClaim)
total_truths = _count(db, PlaceTruth)
grubhub_url = _count(db, Place, Place.grubhub_url.isnot(None))

orphaned_stmt = (
    select(func.count()).select_from(PlaceClaim)
    .outerjoin(Place, PlaceClaim.place_id == Place.id)
    .where(Place.id.is_(None))
)
orphaned_claims = db.execute(orphaned_stmt).scalar_one()

print(f"  TOTAL_PLACES        : {total_places}")
print(f"  ACTIVE_PLACES       : {active_places}")
print(f"  INACTIVE_PLACES     : {total_places - active_places}")
print(f"  WITH_MENU           : {with_menu}")
print(f"  WITH_GRUBHUB_URL    : {grubhub_url}")
print(f"  MISSING_GEO         : {no_geo}")
print(f"  MISSING_SCORE       : {no_score}")
print(f"  TOTAL_CLAIMS        : {total_claims}")
print(f"  TOTAL_TRUTHS        : {total_truths}")
print(f"  ORPHANED_CLAIMS     : {orphaned_claims}")

def check_orphaned():
    return (PASS if orphaned_claims == 0 else FAIL), f"{orphaned_claims} orphaned claims"
check("no orphaned claims", check_orphaned)

def check_missing_score():
    return (WARN if no_score > 0 else PASS), f"{no_score} active places missing score"
check("all active places scored", check_missing_score)

def check_missing_geo():
    return (WARN if no_geo > 0 else PASS), f"{no_geo} active places missing geo"
check("all active places have geo", check_missing_geo)

# ── SECTION 3: SCORING VALIDATION ──────────────────────────────────────
print("\n[3] SCORING VALIDATION")

def check_has_menu_boost():
    from app.services.scoring.recompute import _compute_master_score
    class FakePlace:
        confidence_score = 0.5
        operational_confidence = 0.3
        local_validation = 0.2
        hype_penalty = 0.0
        has_menu = False
    class FakePlaceMenu:
        confidence_score = 0.5
        operational_confidence = 0.3
        local_validation = 0.2
        hype_penalty = 0.0
        has_menu = True
    score_no_menu = _compute_master_score(FakePlace())
    score_with_menu = _compute_master_score(FakePlaceMenu())
    diff = score_with_menu - score_no_menu
    if abs(diff - 0.15) < 0.001:
        return PASS, f"has_menu boost = +{diff:.3f} (correct)"
    return FAIL, f"has_menu boost = +{diff:.3f} (expected +0.150)"
check("has_menu boost = +0.15", check_has_menu_boost)

def check_score_range():
    sample = db.execute(
        select(Place.master_score).where(
            Place.is_active.is_(True),
            Place.master_score.isnot(None),
        ).limit(50)
    ).scalars().all()
    if not sample:
        return WARN, "no scored places to sample"
    max_score = max(sample)
    min_score = min(sample)
    if max_score > 10:
        return FAIL, f"scores look like 0-100 scale (max={max_score:.1f}) — wrong path active"
    return PASS, f"scores in expected range [0,3] min={min_score:.3f} max={max_score:.3f}"
check("score scale correct (0-3 not 0-100)", check_score_range)

# ── SECTION 4: SEARCH VALIDATION ──────────────────────────────────────
print("\n[4] SEARCH VALIDATION")

def check_search_ranker():
    from app.services.search.search_ranker import rank_search_results
    class P:
        rank_score = 0.5
        has_menu = True
        name = "Chipotle"
    class Q:
        rank_score = 0.5
        has_menu = False
        name = "Burritos Inc"
    ranked = rank_search_results([Q(), P()], query="chipotle")
    if ranked[0].name == "Chipotle":
        return PASS, "exact-match + has_menu boost correctly reranks"
    return FAIL, f"ranking incorrect: first={ranked[0].name}"
check("search_ranker exact-match boost works", check_search_ranker)

def check_search_index_build():
    from app.services.search.search_index_builder import build_search_index
    t0 = time.time()
    count = build_search_index(db)
    elapsed = time.time() - t0
    return PASS, f"indexed {count} places in {elapsed:.3f}s"
check("search_index_builder runs", check_search_index_build)

def check_search_query():
    from app.services.search.search_engine import execute_search
    cities = db.execute(select(City).limit(1)).scalars().all()
    if not cities:
        return WARN, "no cities in DB — skipping search query test"
    city_id = cities[0].id
    t0 = time.time()
    results, total = execute_search(db, query="a", city_id=city_id, limit=5)
    elapsed = time.time() - t0
    return PASS, f"search returned {total} total, {len(results)} results in {elapsed*1000:.1f}ms"
check("execute_search runs and returns results", check_search_query)

# ── SECTION 5: CACHE VALIDATION ────────────────────────────────────────
print("\n[5] CACHE VALIDATION")

def check_cache_roundtrip():
    from app.services.cache.cache_client import cache_get, cache_set
    cache_set("phase3_test", {"ok": True}, ttl_seconds=10)
    val = cache_get("phase3_test")
    if val == {"ok": True}:
        return PASS, "cache roundtrip OK"
    return FAIL, f"cache returned {val}"
check("cache roundtrip", check_cache_roundtrip)

def check_cache_helpers():
    from app.services.cache.cache_helpers import get_or_set
    calls = []
    def factory():
        calls.append(1)
        return "value"
    r1 = get_or_set("phase3_gos", factory, ttl_seconds=10)
    r2 = get_or_set("phase3_gos", factory, ttl_seconds=10)
    if r1 == r2 == "value" and len(calls) == 1:
        return PASS, "get_or_set caches correctly (factory called once)"
    return FAIL, f"factory called {len(calls)} times"
check("cache_helpers.get_or_set works", check_cache_helpers)

# ── SECTION 6: DEDUP VALIDATION ────────────────────────────────────────
print("\n[6] DEDUP VALIDATION")

def check_dedup_scorer():
    from app.services.dedup.dedup_scorer import score_place_pair, is_auto_merge
    score = score_place_pair(
        name_a="Chipotle Mexican Grill",
        name_b="Chipotle Mexican Grill",
        lat_a=37.7749, lng_a=-122.4194,
        lat_b=37.7750, lng_b=-122.4195,
    )
    score_diff = score_place_pair(
        name_a="McDonalds",
        name_b="Burger King",
        lat_a=37.7749, lng_a=-122.4194,
        lat_b=37.7749, lng_b=-122.4194,
    )
    if score > 0.7 and not is_auto_merge(score_diff):
        return PASS, f"same={score:.3f} diff={score_diff:.3f}"
    return WARN, f"same={score:.3f} diff={score_diff:.3f}"
check("dedup scorer: identical vs different", check_dedup_scorer)

# ── SECTION 7: INACTIVE PLACES IN SEARCH ──────────────────────────────
print("\n[7] DATA INTEGRITY")

def check_inactive_not_in_search():
    from app.services.query.search_query import search_places
    inactive_count = _count(db, Place, Place.is_active.is_(False))
    if inactive_count == 0:
        return PASS, "no inactive places (nothing to leak)"
    cities = db.execute(select(City).limit(1)).scalars().all()
    if not cities:
        return WARN, "no cities, skipping"
    city_id = cities[0].id
    results, _ = search_places(db, query="a", city_id=city_id, limit=100)
    leaked = [p for p in results if not p.is_active]
    if leaked:
        return FAIL, f"{len(leaked)} inactive places in search results"
    return PASS, f"0 inactive places leaked into search (inactive_total={inactive_count})"
check("inactive places not in search", check_inactive_not_in_search)

def check_menu_truth_integrity():
    # Every PlaceTruth for menu should reference an active place
    from sqlalchemy import and_
    bad = db.execute(
        select(func.count()).select_from(PlaceTruth)
        .join(Place, PlaceTruth.place_id == Place.id)
        .where(Place.is_active.is_(False))
    ).scalar_one()
    return (FAIL if bad > 0 else PASS), f"{bad} truths reference inactive places"
check("truth refs only active places", check_menu_truth_integrity)

# ── SECTION 8: WORKER IMPORT CHECKS ───────────────────────────────────
print("\n[8] WORKER IMPORTS")

workers = [
    ("master_worker", "app.workers.master_worker", "run_master_worker"),
    ("discovery_worker", "app.workers.discovery_worker", "run_discovery_worker"),
    ("truth_rebuild_worker", "app.workers.truth_rebuild_worker", "run_truth_rebuild_worker"),
    ("search_index_worker", "app.workers.search_index_worker", "run_search_index_worker"),
    ("ranking_worker", "app.workers.ranking_worker", "run_worker"),
    ("recompute_scores_worker", "app.workers.recompute_scores_worker", "worker_once"),
    ("feed_refresh_worker", "app.workers.feed_refresh_worker", "refresh_feed"),
    ("run_pipeline", "app.workers.run_pipeline", "run_loop"),
]

for label, module, fn in workers:
    def make_check(m, f):
        def _check():
            mod = importlib.import_module(m)
            getattr(mod, f)
            return PASS, f"{m}.{f} importable"
        return _check
    check(label, make_check(module, fn))

# ── SECTION 9: PERFORMANCE BENCHMARKS ─────────────────────────────────
print("\n[9] PERFORMANCE BENCHMARKS")

def bench_score_recompute():
    from app.services.scoring.recompute import recompute_place_scores
    places = db.execute(select(Place).where(Place.is_active.is_(True)).limit(100)).scalars().all()
    t0 = time.time()
    n = recompute_place_scores(db, places=places)
    elapsed = time.time() - t0
    rate = n / elapsed if elapsed > 0 else 0
    return PASS, f"{n} places in {elapsed:.3f}s = {rate:.0f} places/sec"
check("score recompute throughput", bench_score_recompute)

def bench_dedup_scan():
    from app.services.dedup.place_deduplicator import find_duplicates_in_city
    cities = db.execute(select(City).limit(1)).scalars().all()
    if not cities:
        return WARN, "no cities"
    t0 = time.time()
    report = find_duplicates_in_city(db, cities[0].id)
    elapsed = time.time() - t0
    return PASS, f"checked {report.total_checked} places in {elapsed:.3f}s, found {report.pairs_found} pairs"
check("dedup scan throughput", bench_dedup_scan)

db.close()

# ── FINAL SUMMARY ──────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("  PHASE 3 AUDIT SUMMARY")
print("=" * 70)

passes = sum(1 for _, s, _ in results if s == PASS)
warns  = sum(1 for _, s, _ in results if s == WARN)
fails  = sum(1 for _, s, _ in results if s == FAIL)
total  = len(results)

print(f"\n  PASS: {passes}/{total}")
print(f"  WARN: {warns}/{total}")
print(f"  FAIL: {fails}/{total}")

if fails == 0 and warns == 0:
    verdict = "PRODUCTION READY"
elif fails == 0:
    verdict = "PARTIALLY READY — resolve warnings before deploying"
else:
    verdict = "NOT READY — fix failures before deploying"

print(f"\n  VERDICT: {verdict}")
print("\n" + "=" * 70)

sys.exit(0 if fails == 0 else 1)
```

- [ ] **Step 2: Run the audit script and record baseline**

```bash
python scripts/run_phase3_audit.py 2>&1
```

Expected: All imports PASS, metrics print, scoring validates, 0 failures (possibly some WARN on geo/score gaps).

---

## Task 9: End-to-End Test Matrix

**Files:**
- No file changes — validation only

- [ ] **Test 1: Pipeline guard**

```bash
python run_pipeline_debug.py 2>&1 | grep -E "(COMPLETE|FAIL)"
```

Expected: `PIPELINE COMPLETE — NON-EMPTY MENU MATERIALIZED`

- [ ] **Test 2: Data validation**

```bash
python scripts/run_data_validation.py 2>&1
```

Expected: 2718+ places, 247+ with menu, 0 orphaned claims, minimal warnings.

- [ ] **Test 3: Score recompute throughput**

```bash
python -c "
import time
from app.db.session import SessionLocal
from sqlalchemy import select
from app.db.models.place import Place
from app.services.scoring.recompute import recompute_place_scores
db = SessionLocal()
places = list(db.execute(select(Place).where(Place.is_active.is_(True)).limit(500)).scalars().all())
t0 = time.time()
n = recompute_place_scores(db, places=places)
elapsed = time.time() - t0
print(f'Recomputed {n} places in {elapsed:.3f}s = {n/elapsed:.0f}/sec')
db.close()
"
```

Expected: >100 places/sec

- [ ] **Test 4: Search index build**

```bash
python -c "
import time
from app.db.session import SessionLocal
from app.services.search.search_index_builder import build_search_index
db = SessionLocal()
t0 = time.time()
n = build_search_index(db)
print(f'Indexed {n} places in {time.time()-t0:.3f}s')
db.close()
"
```

Expected: All 2718 active places indexed in <5s

- [ ] **Test 5: Search query latency**

```bash
python -c "
import time
from app.db.session import SessionLocal
from sqlalchemy import select
from app.db.models.city import City
from app.services.search.search_engine import execute_search
db = SessionLocal()
city = db.execute(select(City).limit(1)).scalar_one()
t0 = time.time()
results, total = execute_search(db, query='taco', city_id=city.id, limit=10)
elapsed = time.time() - t0
print(f'Search: {total} total, {len(results)} returned in {elapsed*1000:.1f}ms')
for r in results[:3]:
    print(f'  {r.name} score={r.rank_score:.4f} has_menu={r.has_menu}')
db.close()
"
```

Expected: <100ms, results ordered by rank_score desc

- [ ] **Test 6: Dedup audit (dry run)**

```bash
python scripts/run_dedup_audit.py 2>&1 | head -20
```

Expected: Scan completes, shows pair counts, no crash

- [ ] **Test 7: Truth rebuild (single place)**

```bash
python -c "
from app.db.session import SessionLocal
from sqlalchemy import select
from app.db.models.place import Place
from app.services.truth.truth_resolver_v2 import resolve_place_truths_v2
db = SessionLocal()
place = db.execute(select(Place).where(Place.has_menu.is_(True)).limit(1)).scalar_one()
truths = resolve_place_truths_v2(db=db, place_id=place.id)
db.commit()
print(f'Rebuilt {len(truths)} truths for {place.name}')
db.close()
"
```

Expected: >0 truths rebuilt

- [ ] **Test 8: Cache invalidation**

```bash
python -c "
from app.services.cache.cache_helpers import get_or_set, invalidate_place
calls = []
val1 = get_or_set('test_k', lambda: (calls.append(1) or 42), ttl_seconds=60)
val2 = get_or_set('test_k', lambda: (calls.append(1) or 99), ttl_seconds=60)
print(f'val1={val1} val2={val2} factory_calls={len(calls)}')
assert val1 == val2 == 42 and len(calls) == 1
print('PASS')
"
```

Expected: `PASS`

- [ ] **Test 9: Dedup merger (dry run)**

```bash
python -c "
from app.db.session import SessionLocal
from sqlalchemy import select
from app.db.models.place import Place
from app.services.dedup.dedup_merger import merge_duplicate_places
db = SessionLocal()
places = db.execute(select(Place).limit(2)).scalars().all()
a, b = places[0], places[1]
winner = merge_duplicate_places(db, place_a_id=a.id, place_b_id=b.id, dry_run=True)
print(f'dry_run winner={winner} (no DB writes)')
db.close()
"
```

Expected: Returns a winner ID, no DB changes.

- [ ] **Test 10: Worker imports + idempotency**

```bash
python -c "
from app.workers.master_worker import run_master_worker
from app.workers.discovery_worker import run_discovery_worker
from app.workers.truth_rebuild_worker import run_truth_rebuild_worker
from app.workers.search_index_worker import run_search_index_worker
from app.workers.ranking_worker import run_worker
from app.workers.recompute_scores_worker import worker_once
from app.workers.feed_refresh_worker import refresh_feed
from app.workers.run_pipeline import run_loop
print('ALL WORKERS IMPORT OK')
# Idempotency: run score recompute twice on same data
from app.db.session import SessionLocal
from sqlalchemy import select
from app.db.models.place import Place
from app.services.scoring.recompute import recompute_place_scores
db = SessionLocal()
places = list(db.execute(select(Place).limit(10)).scalars().all())
n1 = recompute_place_scores(db, places=places)
scores1 = [p.rank_score for p in places]
n2 = recompute_place_scores(db, places=places)
scores2 = [p.rank_score for p in places]
assert scores1 == scores2, 'scores drifted on second run!'
print(f'IDEMPOTENCY PASS — scores stable across 2 runs, n={n1}')
db.close()
"
```

Expected: `ALL WORKERS IMPORT OK` then `IDEMPOTENCY PASS`

---

## Task 10: Run Full Audit Script and Record Final Verdict

- [ ] **Step 1: Run full audit**

```bash
python scripts/run_phase3_audit.py 2>&1
```

- [ ] **Step 2: Run pipeline guard one final time**

```bash
python run_pipeline_debug.py 2>&1 | tail -5
```

Expected: `PIPELINE COMPLETE — NON-EMPTY MENU MATERIALIZED`

- [ ] **Step 3: Print final system command reference**

```
RUN BACKEND:
    uvicorn app.main:app --host 0.0.0.0 --port 8000

RUN MASTER WORKER:
    python app/workers/run_master_worker.py

RUN DISCOVERY ONLY:
    python -c "from app.workers.discovery_worker import run_discovery_worker; run_discovery_worker()"

RUN MENU INGESTION ONLY:
    python scripts/run_menu_worker.py

RUN DEDUP AUDIT:
    python scripts/run_dedup_audit.py

REBUILD TRUTH:
    python -c "from app.workers.truth_rebuild_worker import run_truth_rebuild_worker; run_truth_rebuild_worker()"

RECOMPUTE SCORES:
    python app/workers/recompute_scores_worker.py

REBUILD SEARCH INDEX:
    python -c "from app.db.session import SessionLocal; from app.services.search.search_index_builder import build_search_index; db=SessionLocal(); print(build_search_index(db)); db.close()"

TEST SEARCH:
    python scripts/run_phase3_audit.py

VALIDATE DATA:
    python scripts/run_data_validation.py

FULL AUDIT:
    python scripts/run_phase3_audit.py
```

---

## Self-Review

**Spec coverage check:**
- ✓ Step 1 (system trace): documented in confirmed bugs table + task descriptions
- ✓ Step 2 (active vs legacy): run_pipeline deprecated, score_all_places_v2 documented
- ✓ Step 3 (worker stress test): Task 10 tests idempotency + all worker imports
- ✓ Step 4 (failure paths): audit script covers orphaned claims, inactive leak, bad data
- ✓ Step 5 (performance): Tasks 9 benchmarks score/search/dedup throughput
- ✓ Step 6 (cache): Task 5 + audit script section 5
- ✓ Step 7 (data consistency): audit script section 7
- ✓ Step 8 (scoring/search): audit script sections 3+4, Task 2
- ✓ Step 9 (API routing): imports validate all routes compile clean
- ✓ Step 10 (cleanup): Task 1 deprecates run_pipeline, Task 7 documents orphan
- ✓ Step 11 (e2e matrix): Task 9 has 10 numbered tests
- ✓ Step 12 (metrics): audit script section 2 prints all required metrics
- ✓ Step 13 (verdict): audit script final summary prints verdict

**Placeholder scan:** No TBDs, no "fill in later" — all code is complete.

**Type consistency:** `execute_search()` signature matches between search_engine.py and search.py usage.
