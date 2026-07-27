"""
discover_menu_sources.py

Phase 2B (discovery) → Phase 2 (ingestion) auto-chain.

Discovery:
  - Probes Place.website to find highest-quality menu_source_url
  - Multi-path probing: /, /menu, /order, /order-online, /online-order, /food, /eat
  - Early stop: stops probing a place as soon as a provider is detected
  - Domain cache: skips "not_found" domains for 24h, reuses "found" immediately
  - Raw HTML provider scan: toasttab, square.site, popmenu, chownow
  - Smart link filtering: keeps menu/order keywords, rejects social/admin/aggregators
  - Scores: toast=100, popmenu=90, square=80, chownow=70, /menu=40
  - Blocks: grubhub, ubereats, doordash, yelp, seamless, clover homepage
  - Saves ONE best URL per place

Ingestion (auto-chains after discovery unless --discover-only):
  - Runs MasterDataOrchestrator.ensure_place() on every discovered place
  - Reports coverage delta

Usage:
    python scripts/discover_menu_sources.py --dry-run
    python scripts/discover_menu_sources.py --limit 100
    python scripts/discover_menu_sources.py --limit 500 --discover-only
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, update, text

from app.db.session import SessionLocal
from app.db.models.place import Place
from app.services.menu.discovery.website_provider_probe import probe_website, ProbeResult
from app.services.menu.discovery.website_provider_probe import _score_url, _normalize_url


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Phase 2B: Domain Cache ────────────────────────────────────────────────────
# Prevents re-probing dead/already-found domains within TTL window.
# Thread-safe via _domain_cache_lock.

_domain_cache: dict[str, dict] = {}
# schema: domain -> {"status": "found"|"not_found", "timestamp": datetime}

_domain_cache_lock = threading.Lock()
_DOMAIN_CACHE_TTL_FOUND = timedelta(hours=24 * 7)   # reuse found results for 7 days
_DOMAIN_CACHE_TTL_NOT_FOUND = timedelta(hours=24)    # skip not_found for 24h


def _domain_cache_get(domain: str) -> str | None:
    """
    Returns "found", "not_found", or None (not cached / expired).
    """
    with _domain_cache_lock:
        entry = _domain_cache.get(domain)
        if not entry:
            return None
        status = entry["status"]
        ttl = _DOMAIN_CACHE_TTL_FOUND if status == "found" else _DOMAIN_CACHE_TTL_NOT_FOUND
        if datetime.utcnow() - entry["timestamp"] > ttl:
            del _domain_cache[domain]
            return None
        return status


def _domain_cache_set(domain: str, status: str) -> None:
    with _domain_cache_lock:
        _domain_cache[domain] = {"status": status, "timestamp": datetime.utcnow()}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _domain(website: str) -> str:
    try:
        return urlparse(website).netloc.lower()
    except Exception:
        return website[:60]


def _db_coverage(db) -> tuple[int, int, int]:
    """Returns (menu_items_total, places_with_menu, active_places)."""
    items = db.execute(text("SELECT COUNT(*) FROM menu_items")).scalar() or 0
    places_with = db.execute(
        text("SELECT COUNT(DISTINCT place_id) FROM menu_items")
    ).scalar() or 0
    active = db.execute(
        text("SELECT COUNT(*) FROM places WHERE is_active = true")
    ).scalar() or 0
    return items, places_with, active


# ── Phase 1: Discovery ────────────────────────────────────────────────────────

def run_discovery(
    db,
    *,
    limit: int,
    dry_run: bool,
    workers: int = 12,
) -> list[str]:
    """
    Probe websites in parallel, save menu_source_url for high-scoring results.
    Returns list of place_ids that got a URL saved.
    """
    rows = db.execute(
        text("""
            SELECT id, name, website, rank_score
            FROM places
            WHERE is_active = true
              AND website IS NOT NULL
              AND website != ''
              AND has_menu = false
              AND menu_source_url IS NULL
            ORDER BY
              CASE
                WHEN website LIKE '%toasttab.com%'  THEN 1
                WHEN website LIKE '%popmenu.com%'   THEN 2
                WHEN website LIKE '%square.site%'   THEN 3
                WHEN website LIKE '%chownow.com%'   THEN 4
                ELSE 5
              END ASC,
              rank_score DESC
            LIMIT :limit
        """),
        {"limit": limit},
    ).fetchall()

    print(f"\n=== PHASE 1: DISCOVERY ===")
    print(f"Candidates: {len(rows)}", flush=True)
    if dry_run:
        print("DRY RUN — no DB writes\n", flush=True)
    else:
        print(flush=True)

    discovered_ids: list[str] = []
    found_count = 0
    skipped_count = 0

    def _probe_row(row) -> tuple:
        """
        Returns (row, ProbeResult) — runs in thread pool.

        Phase 2B: checks domain cache before probing.
          - If domain is "found" in cache  → re-probe anyway (URL may differ per place).
          - If domain is "not_found" in cache within TTL → skip immediately.
        """
        website = (row.website or "").strip()
        if not website:
            return row, None

        domain = _domain(website)
        cached_status = _domain_cache_get(domain)

        if cached_status == "not_found":
            # Domain known-dead within TTL — skip without HTTP
            logger.debug("domain_cache_skip domain=%s", domain)
            return row, ProbeResult(menu_source_url=None, provider=None, score=0, confidence=0.0)

        result = probe_website(website)

        # Update domain cache
        _domain_cache_set(domain, "found" if result.found else "not_found")

        return row, result

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_probe_row, row): row for row in rows}
        pending_writes: list[tuple] = []

        for future in as_completed(futures):
            row, result = future.result()
            website = (row.website or "").strip()
            if not website or result is None:
                skipped_count += 1
                continue

            if not result.found:
                skipped_count += 1
                print(
                    f"  SKIP  {row.name!r:40s}  score={result.score}  "
                    f"({result.provider or 'none'})",
                    flush=True,
                )
                continue

            found_count += 1
            print(
                f"  FOUND {row.name!r:40s}  score={result.score:>3}  "
                f"{result.provider:<10}  {result.menu_source_url}",
                flush=True,
            )

            if dry_run:
                continue

            pending_writes.append((row.id, result.menu_source_url[:1024]))

            # Batch commit every 20 saves
            if len(pending_writes) >= 20:
                for pid, murl in pending_writes:
                    db.execute(
                        update(Place)
                        .where(Place.id == pid)
                        .values(menu_source_url=murl)
                    )
                db.commit()
                for pid, _ in pending_writes:
                    discovered_ids.append(pid)
                pending_writes.clear()

    # Flush remaining
    if pending_writes and not dry_run:
        for pid, murl in pending_writes:
            db.execute(
                update(Place)
                .where(Place.id == pid)
                .values(menu_source_url=murl)
            )
        db.commit()
        for pid, _ in pending_writes:
            discovered_ids.append(pid)

    print(f"\nDiscovery: {found_count} found, {skipped_count} skipped", flush=True)
    return discovered_ids


# ── Phase 1b: Retry ingestion for places with saved URL but no menu ───────────

def get_retry_ids(db, limit: int = 500) -> list[str]:
    """
    Places that have a menu_source_url (discovery ran) but has_menu=false (ingestion
    failed or was never run). Re-run ingestion — no probing needed.
    """
    rows = db.execute(
        text("""
            SELECT id
            FROM places
            WHERE is_active = true
              AND menu_source_url IS NOT NULL
              AND menu_source_url != ''
              AND has_menu = false
            ORDER BY rank_score DESC
            LIMIT :limit
        """),
        {"limit": limit},
    ).fetchall()
    return [r[0] for r in rows]


# ── Phase 2: Ingestion ────────────────────────────────────────────────────────

def run_ingestion(db, place_ids: list[str]) -> None:
    """Run MasterDataOrchestrator on each discovered place."""
    from app.services.data.master_data_orchestrator import MasterDataOrchestrator, MasterDataResult

    print(f"\n=== PHASE 2: INGESTION ===")
    print(f"Targets: {len(place_ids)}\n")

    orchestrator = MasterDataOrchestrator()
    succeeded = 0
    failed = 0
    total_items = 0

    for i, place_id in enumerate(place_ids, 1):
        place = db.query(Place).filter(Place.id == place_id).first()
        if not place:
            failed += 1
            continue

        try:
            result: MasterDataResult = orchestrator.ensure_place(db=db, place=place)
            items_added = max(result.menu_items_after - result.menu_items_before, 0)
            ok = result.menu_action in ("extracted", "fallback")

            if ok:
                succeeded += 1
                total_items += items_added
            else:
                failed += 1

            status = "✓" if ok else "✗"
            print(
                f"  [{i:>4}/{len(place_ids)}] {status} "
                f"{(getattr(place, 'name', None) or place_id)[:40]:<40}  "
                f"action={result.menu_action:<10}  items_added={items_added:>4}",
                flush=True,
            )

            if result.errors:
                for err in result.errors:
                    print(f"        ERR: {err}", flush=True)

        except Exception as exc:
            failed += 1
            print(f"  [{i:>4}/{len(place_ids)}] ✗ {place_id}  EXCEPTION: {exc}", flush=True)

        if i % 10 == 0:
            try:
                db.commit()
            except Exception:
                db.rollback()

    try:
        db.commit()
    except Exception:
        db.rollback()

    print(f"\nIngestion: {succeeded} succeeded, {failed} failed, {total_items} items added")


# ── Main ──────────────────────────────────────────────────────────────────────

def main(*, dry_run: bool, limit: int, discover_only: bool, workers: int) -> None:
    db = SessionLocal()

    try:
        items_before, places_before, active = _db_coverage(db)
        print(f"DB before: {items_before:,} items | {places_before}/{active} places ({places_before/active*100:.1f}%)")

        # Phase 1 — Discovery (only targets places with no menu_source_url yet)
        discovered_ids = run_discovery(db, limit=limit, dry_run=dry_run, workers=workers)

        if dry_run:
            print("\nDRY RUN — skipping ingestion")
            return

        if discover_only:
            print(f"\n--discover-only: skipping ingestion ({len(discovered_ids)} URLs saved)")
            _report(db)
            return

        # Phase 1b — Retry: places already have menu_source_url but ingestion failed
        retry_ids = get_retry_ids(db, limit=limit)
        if retry_ids:
            print(f"\n=== PHASE 1b: INGESTION RETRY ===")
            print(f"Places with saved URL but no menu: {len(retry_ids)}")
            run_ingestion(db, retry_ids)

        # Phase 2 — Ingestion (auto-chain for newly discovered)
        if not discovered_ids:
            print("\nNothing newly discovered")
        else:
            run_ingestion(db, discovered_ids)

        # Reporting
        _report(db)

    finally:
        db.close()


def _report(db) -> None:
    print("\n=== COVERAGE REPORT ===")
    row = db.execute(text("""
        SELECT
          COUNT(DISTINCT place_id) as places_with_menus,
          COUNT(*) as total_items,
          (SELECT COUNT(*) FROM places WHERE is_active = true) as total_places,
          ROUND(COUNT(DISTINCT place_id) * 100.0 /
            NULLIF((SELECT COUNT(*) FROM places WHERE is_active = true), 0), 1) as coverage_pct
        FROM menu_items
    """)).fetchone()
    if row:
        print(f"  places_with_menus : {row[0]:,}")
        print(f"  total_items       : {row[1]:,}")
        print(f"  total_places      : {row[2]:,}")
        print(f"  coverage_pct      : {row[3]}%")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Discover menu sources + chain ingestion")
    parser.add_argument("--dry-run", action="store_true", help="Probe only, no DB writes")
    parser.add_argument("--limit", type=int, default=100, help="Max places to probe")
    parser.add_argument("--discover-only", action="store_true", help="Save URLs but skip ingestion")
    parser.add_argument("--workers", type=int, default=12, help="Parallel probe workers (default 12)")
    args = parser.parse_args()
    main(dry_run=args.dry_run, limit=args.limit, discover_only=args.discover_only, workers=args.workers)
