#!/usr/bin/env python3
"""
Phase 3 Full System Audit Script.

Runs all validation checks and prints a complete production-readiness report.

Usage:
    python scripts/run_phase3_audit.py

Exit codes:
    0 = all checks PASS or WARN only
    1 = one or more FAIL
"""
from __future__ import annotations

import sys
import os
import time
import importlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, func
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
    return PASS, "run_pipeline imports cleanly (deprecated shim)"
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
    from app.workers.ranking_worker import run_worker, MAX_ERRORS
    return PASS, f"ranking_worker imports cleanly MAX_ERRORS={MAX_ERRORS}"
check("ranking_worker import", check_ranking_worker)


def check_search_route_wired():
    src = open("app/api/v1/routes/search.py").read()
    if "execute_search" in src and "from app.services.query.search_query" not in src:
        return PASS, "search route uses execute_search (Phase 1 ranking active)"
    return FAIL, "search route still bypasses search_engine.py"
check("search route wired to search_engine", check_search_route_wired)


def check_places_route_guarded():
    src = open("app/api/v1/routes/places.py").read()
    if "HTTPException" in src and "except Exception" in src:
        return PASS, "places route has error handling"
    return WARN, "places route may lack error handling"
check("places route error-guarded", check_places_route_guarded)


# ── SECTION 2: DATABASE METRICS ────────────────────────────────────────
print("\n[2] DATABASE METRICS")

total_places = _count(db, Place)
active_places = _count(db, Place, Place.is_active.is_(True))
inactive_places = total_places - active_places
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

# avg menu items (count claims with field="menu" as proxy)
avg_items_row = db.execute(
    select(func.count(PlaceClaim.id))
    .where(PlaceClaim.field == "menu")
).scalar_one()
avg_items = round(avg_items_row / with_menu, 1) if with_menu else 0

print(f"  TOTAL_PLACES        : {total_places}")
print(f"  ACTIVE_PLACES       : {active_places}")
print(f"  INACTIVE_PLACES     : {inactive_places}")
print(f"  WITH_MENU           : {with_menu}")
print(f"  WITH_GRUBHUB_URL    : {grubhub_url}")
print(f"  MISSING_GEO         : {no_geo}")
print(f"  MISSING_SCORE       : {no_score}")
print(f"  TOTAL_CLAIMS        : {total_claims}")
print(f"  TOTAL_TRUTHS        : {total_truths}")
print(f"  ORPHANED_CLAIMS     : {orphaned_claims}")
print(f"  AVG_MENU_ITEMS      : {avg_items} (across {with_menu} menu places)")


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
    diff = round(score_with_menu - score_no_menu, 4)
    if abs(diff - 0.15) < 0.001:
        return PASS, f"has_menu boost = +{diff:.3f} (correct)"
    return FAIL, f"has_menu boost = +{diff:.3f} (expected +0.150)"
check("has_menu boost = +0.15", check_has_menu_boost)


def check_score_idempotency():
    from app.services.scoring.recompute import recompute_place_scores
    places = list(db.execute(select(Place).where(Place.is_active.is_(True)).limit(20)).scalars().all())
    if not places:
        return WARN, "no active places to test"
    recompute_place_scores(db, places=places)
    scores1 = [round(p.rank_score or 0, 6) for p in places]
    recompute_place_scores(db, places=places)
    scores2 = [round(p.rank_score or 0, 6) for p in places]
    if scores1 == scores2:
        return PASS, f"scores stable across 2 runs (n={len(places)})"
    return FAIL, "scores drifted between runs — not idempotent"
check("score recompute is idempotent", check_score_idempotency)


def check_score_range():
    sample = list(db.execute(
        select(Place.master_score).where(
            Place.is_active.is_(True),
            Place.master_score.isnot(None),
        ).limit(100)
    ).scalars().all())
    if not sample:
        return WARN, "no scored places to sample"
    max_score = max(sample)
    min_score = min(sample)
    if max_score > 10:
        return FAIL, f"scores look like 0-100 scale (max={max_score:.1f}) — wrong path active"
    return PASS, f"scores in expected range min={min_score:.4f} max={max_score:.4f}"
check("score scale correct (not 0-100)", check_score_range)


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
        return PASS, "exact-match + has_menu boost correctly reranks results"
    return FAIL, f"ranking incorrect: first={ranked[0].name} (expected Chipotle)"
check("search_ranker exact-match boost", check_search_ranker)


def check_search_index_build():
    from app.services.search.search_index_builder import build_search_index
    t0 = time.time()
    count = build_search_index(db)
    elapsed = time.time() - t0
    return PASS, f"indexed {count} places in {elapsed:.3f}s"
check("search_index_builder runs", check_search_index_build)


def check_search_execute():
    from app.services.search.search_engine import execute_search
    cities = list(db.execute(select(City).limit(1)).scalars().all())
    if not cities:
        return WARN, "no cities in DB — skipping"
    city_id = cities[0].id
    t0 = time.time()
    results, total = execute_search(db, query="a", city_id=city_id, limit=10)
    elapsed = (time.time() - t0) * 1000
    return PASS, f"returned {total} total, {len(results)} results in {elapsed:.1f}ms"
check("execute_search returns results", check_search_execute)


def check_search_inactive_excluded():
    from app.services.search.search_engine import execute_search
    cities = list(db.execute(select(City).limit(1)).scalars().all())
    if not cities:
        return WARN, "no cities"
    city_id = cities[0].id
    results, _ = execute_search(db, query="a", city_id=city_id, limit=200)
    leaked = [p for p in results if not p.is_active]
    if leaked:
        return FAIL, f"{len(leaked)} inactive places in search results"
    return PASS, f"0 inactive places in search results"
check("inactive places excluded from search", check_search_inactive_excluded)


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


def check_cache_ttl_expiry():
    from app.services.cache.response_cache import response_cache
    import time
    response_cache.set("phase3_ttl_test", "expires", ttl_seconds=1)
    assert response_cache.get("phase3_ttl_test") == "expires"
    time.sleep(1.1)
    val = response_cache.get("phase3_ttl_test")
    if val is None:
        return PASS, "TTL expiry works correctly"
    return FAIL, f"value still present after TTL: {val}"
check("cache TTL expiry", check_cache_ttl_expiry)


def check_cache_helpers_get_or_set():
    from app.services.cache.cache_helpers import get_or_set, invalidate
    calls = []
    r1 = get_or_set("phase3_gos", lambda: (calls.append(1) or 42), ttl_seconds=10)
    r2 = get_or_set("phase3_gos", lambda: (calls.append(1) or 99), ttl_seconds=10)
    invalidate("phase3_gos")
    r3 = get_or_set("phase3_gos", lambda: (calls.append(1) or 77), ttl_seconds=10)
    if r1 == r2 == 42 and r3 == 77 and len(calls) == 2:
        return PASS, "get_or_set: factory called once, re-called after invalidate"
    return FAIL, f"factory_calls={len(calls)} r1={r1} r2={r2} r3={r3}"
check("cache_helpers.get_or_set works", check_cache_helpers_get_or_set)


# ── SECTION 6: DATA INTEGRITY ──────────────────────────────────────────
print("\n[6] DATA INTEGRITY")


def check_truth_refs_active():
    bad = db.execute(
        select(func.count()).select_from(PlaceTruth)
        .join(Place, PlaceTruth.place_id == Place.id)
        .where(Place.is_active.is_(False))
    ).scalar_one()
    return (FAIL if bad > 0 else PASS), f"{bad} truths reference inactive places"
check("truth refs only active places", check_truth_refs_active)


def check_menu_places_have_truths():
    menu_with_no_truth = db.execute(
        select(func.count()).select_from(Place)
        .outerjoin(PlaceTruth, Place.id == PlaceTruth.place_id)
        .where(Place.has_menu.is_(True))
        .where(PlaceTruth.id.is_(None))
    ).scalar_one()
    if menu_with_no_truth > 0:
        return WARN, f"{menu_with_no_truth} places with has_menu=True but no PlaceTruth rows"
    return PASS, "all menu places have truth records"
check("menu places have truth records", check_menu_places_have_truths)


# ── SECTION 7: WORKER IMPORTS ──────────────────────────────────────────
print("\n[7] WORKER IMPORTS")

workers = [
    ("master_worker", "app.workers.master_worker", "run_master_worker"),
    ("discovery_worker", "app.workers.discovery_worker", "run_discovery_worker"),
    ("truth_rebuild_worker", "app.workers.truth_rebuild_worker", "run_truth_rebuild_worker"),
    ("search_index_worker", "app.workers.search_index_worker", "run_search_index_worker"),
    ("ranking_worker", "app.workers.ranking_worker", "run_worker"),
    ("recompute_scores_worker", "app.workers.recompute_scores_worker", "worker_once"),
    ("feed_refresh_worker", "app.workers.feed_refresh_worker", "refresh_feed"),
    ("run_pipeline (deprecated)", "app.workers.run_pipeline", "run_loop"),
    ("run_master_worker", "app.workers.run_master_worker", "main"),
]

for label, module, fn in workers:
    def _make(m, f, lbl):
        def _check():
            mod = importlib.import_module(m)
            getattr(mod, f)
            return PASS, f"{lbl} importable"
        return _check
    check(label, _make(module, fn, label))


# ── SECTION 8: PERFORMANCE BENCHMARKS ─────────────────────────────────
print("\n[8] PERFORMANCE BENCHMARKS")


def bench_score_recompute():
    from app.services.scoring.recompute import recompute_place_scores
    places = list(db.execute(select(Place).where(Place.is_active.is_(True)).limit(200)).scalars().all())
    t0 = time.time()
    n = recompute_place_scores(db, places=places)
    elapsed = time.time() - t0
    rate = n / elapsed if elapsed > 0 else 0
    status = PASS if rate > 50 else WARN
    return status, f"{n} places in {elapsed:.3f}s = {rate:.0f} places/sec"
check("score recompute throughput", bench_score_recompute)


def bench_search_index():
    from app.services.search.search_index_builder import build_search_index
    t0 = time.time()
    n = build_search_index(db)
    elapsed = time.time() - t0
    return PASS, f"indexed {n} places in {elapsed:.3f}s"
check("search index build speed", bench_search_index)


def bench_dedup_scan():
    from app.services.dedup.place_deduplicator import find_duplicates_in_city
    cities = list(db.execute(select(City).limit(1)).scalars().all())
    if not cities:
        return WARN, "no cities"
    t0 = time.time()
    report = find_duplicates_in_city(db, cities[0].id)
    elapsed = time.time() - t0
    return PASS, f"checked {report.total_checked} places in {elapsed:.3f}s, found {report.pairs_found} pairs"
check("dedup scan throughput", bench_dedup_scan)


def bench_search_latency():
    from app.services.search.search_engine import execute_search
    cities = list(db.execute(select(City).limit(1)).scalars().all())
    if not cities:
        return WARN, "no cities"
    city_id = cities[0].id
    # Run 5 searches, measure avg
    queries = ["a", "taco", "burger", "pizza", "chi"]
    times = []
    for q in queries:
        t0 = time.time()
        execute_search(db, query=q, city_id=city_id, limit=20)
        times.append((time.time() - t0) * 1000)
    avg_ms = sum(times) / len(times)
    status = PASS if avg_ms < 200 else WARN
    return status, f"avg search latency {avg_ms:.1f}ms over {len(queries)} queries"
check("search latency", bench_search_latency)


db.close()

# ── ACTIVE VS LEGACY PATH SUMMARY ─────────────────────────────────────
print("\n[9] ACTIVE vs LEGACY PATH CLASSIFICATION")

paths = [
    ("ACTIVE",    "master_worker.py",              "discovery + menu + image crawl, 30s loop"),
    ("ACTIVE",    "discovery_worker.py",            "standalone discovery, 120s loop"),
    ("ACTIVE",    "truth_rebuild_worker.py",        "truth rebuild, 600s loop"),
    ("ACTIVE",    "search_index_worker.py",         "search index, 900s loop"),
    ("ACTIVE",    "ranking_worker.py",              "city ranking snapshot, 3600s loop"),
    ("ACTIVE",    "recompute_scores_worker.py",     "queue-based score recompute"),
    ("ACTIVE",    "feed_refresh_worker.py",         "feed warming worker"),
    ("ACTIVE",    "image_crawler_worker.py",        "image crawl, 300s loop"),
    ("ACTIVE",    "run_master_worker.py",           "entrypoint for master_worker"),
    ("DEPRECATED","run_pipeline.py",               "shim → master_worker (import fixed)"),
    ("ORPHANED",  "score_all_places_v2.py",        "needs_recompute never set; scale conflict with recompute.py"),
    ("ORPHANED",  "search_service.py",              "empty stub — unused"),
    ("ORPHANED",  "feed_service.py",                "empty stub — unused"),
    ("ORPHANED",  "scripts/run_rank_places.py",     "empty stub"),
    ("ORPHANED",  "scripts/run_score_rebuild_v2.py","empty stub"),
    ("ORPHANED",  "scripts/run_search_index.py",    "empty stub"),
    ("ORPHANED",  "scripts/run_truth_rebuild_v2.py","empty stub"),
    ("ORPHANED",  "scripts/run_image_crawler.py",   "empty stub"),
]

for status, path, note in paths:
    tag = {"ACTIVE": "✓", "DEPRECATED": "→", "ORPHANED": "○"}.get(status, "?")
    print(f"  {tag} [{status:<10}] {path:<40} {note}")


# ── FINAL SUMMARY ──────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("  PHASE 3 AUDIT SUMMARY")
print("=" * 70)

passes = sum(1 for _, s, _ in results if s == PASS)
warns  = sum(1 for _, s, _ in results if s == WARN)
fails  = sum(1 for _, s, _ in results if s == FAIL)
total  = len(results)

print(f"\n  PASS : {passes}/{total}")
print(f"  WARN : {warns}/{total}")
print(f"  FAIL : {fails}/{total}")

if fails == 0 and warns == 0:
    verdict = "PRODUCTION READY"
elif fails == 0:
    verdict = "PARTIALLY READY — resolve warnings before deploying"
else:
    verdict = "NOT READY — fix failures before deploying"

print(f"\n  VERDICT: {verdict}")

print("""
──────────────────────────────────────────────────────────────────────
  COMMAND REFERENCE
──────────────────────────────────────────────────────────────────────
  Run backend:        uvicorn app.main:app --host 0.0.0.0 --port 8000
  Run master worker:  python app/workers/run_master_worker.py
  Run discovery:      python -c "from app.workers.discovery_worker import run_discovery_worker; run_discovery_worker()"
  Run menu ingest:    python scripts/run_menu_worker.py
  Run dedup audit:    python scripts/run_dedup_audit.py
  Rebuild truth:      python -c "from app.workers.truth_rebuild_worker import run_truth_rebuild_worker; run_truth_rebuild_worker()"
  Recompute scores:   python app/workers/recompute_scores_worker.py
  Rebuild search idx: python -c "from app.db.session import SessionLocal; from app.services.search.search_index_builder import build_search_index; db=SessionLocal(); print(build_search_index(db)); db.close()"
  Data validation:    python scripts/run_data_validation.py
  Full audit:         python scripts/run_phase3_audit.py
──────────────────────────────────────────────────────────────────────
""")

print("=" * 70)

sys.exit(0 if fails == 0 else 1)
