#!/usr/bin/env python3
"""
run_saturation.py
=================
Full data saturation runner for CRAVE backend.

Phases:
  1. Validate Grubhub cookies (fast check before committing)
  2. Reset all retryable failed jobs → pending
  3. Queue jobs for places with grubhub_url but no job
  4. Run menu ingestion in batches until queue is empty
  5. Print final metrics

Usage
-----
    # Load cookies and run:
    source backend/.grubhub_env && python backend/scripts/run_saturation.py

    # Limit places processed per run:
    source backend/.grubhub_env && python backend/scripts/run_saturation.py --limit 50

    # Skip URL discovery (just process queued jobs):
    source backend/.grubhub_env && python backend/scripts/run_saturation.py --skip-discovery

    # Dry-run (show counts without making changes):
    python backend/scripts/run_saturation.py --dry-run

Notes
-----
- Cookies expire every few hours. Re-run grab_grubhub_cookies.py if you get 401s.
- Runs in a single process; no concurrency needed.
- Idempotent: safe to run multiple times.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# ── Load .grubhub_env ─────────────────────────────────────────────────────────
_env_file = ROOT_DIR / "backend" / ".grubhub_env"
if _env_file.exists():
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line.startswith("export "):
                line = line[7:]
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("run_saturation")

BATCH_SIZE = 15          # places per ingestion batch
MAX_BATCHES = 999        # safety: stop after this many batches
SLEEP_BETWEEN_BATCHES = 2  # seconds between batches (rate limiting)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _print(msg: str) -> None:
    ts = _utcnow().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 0: PRINT BANNER
# ─────────────────────────────────────────────────────────────────────────────

def print_banner() -> None:
    print("=" * 70)
    print("  CRAVE DATA SATURATION RUNNER")
    print("=" * 70)


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1: COOKIE VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

def validate_cookies() -> bool:
    """
    Fast check: does GRUBHUB_COOKIES exist AND does a test fetch return non-401?
    Returns True if cookies appear valid.
    """
    cookies = os.environ.get("GRUBHUB_COOKIES", "").strip()
    px = os.environ.get("GRUBHUB_PERIMETER_X", "").strip()

    if not cookies:
        _print("COOKIE_CHECK: FAIL — GRUBHUB_COOKIES not set")
        _print("  Run: python backend/scripts/grab_grubhub_cookies.py")
        _print("  Then: source backend/.grubhub_env && python backend/scripts/run_saturation.py")
        return False

    _print(f"COOKIE_CHECK: cookies={len(cookies)} chars, perimeter_x={len(px)} chars")

    # Quick live test against a known restaurant
    try:
        from app.services.menu.fetchers.grubhub_fetcher import _load_grubhub_cookies, _load_perimeter_x
        from curl_cffi import requests as cffi_requests

        loaded = _load_grubhub_cookies()
        if not loaded:
            _print("COOKIE_CHECK: FAIL — could not parse GRUBHUB_COOKIES")
            return False

        perimeter_x = _load_perimeter_x()
        session = cffi_requests.Session(impersonate="chrome110")
        session.cookies.update(loaded)

        headers = {
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://www.grubhub.com",
        }
        if perimeter_x:
            headers["perimeter-x"] = perimeter_x

        # Test with a simple known endpoint
        resp = session.get(
            "https://api-gtm.grubhub.com/restaurants/2422189",
            headers=headers,
            timeout=10,
            allow_redirects=False,
        )
        _print(f"COOKIE_CHECK: HTTP {resp.status_code}")

        if resp.status_code == 401:
            _print("COOKIE_CHECK: FAIL — 401 (cookies expired)")
            _print("")
            _print("  *** COOKIES EXPIRED — MUST REFRESH ***")
            _print("  Run: python backend/scripts/grab_grubhub_cookies.py")
            _print("  Then: source backend/.grubhub_env && python backend/scripts/run_saturation.py")
            return False

        if resp.status_code == 403:
            _print("COOKIE_CHECK: FAIL — 403 (PerimeterX block)")
            _print("  Re-run grab_grubhub_cookies.py with a different URL or wait 10 minutes")
            return False

        _print(f"COOKIE_CHECK: PASS (HTTP {resp.status_code})")
        return True

    except Exception as exc:
        _print(f"COOKIE_CHECK: ERROR — {exc}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2: RESET FAILED JOBS
# ─────────────────────────────────────────────────────────────────────────────

def reset_failed_jobs(db, dry_run: bool = False) -> int:
    """
    Reset retryable failed menu jobs back to pending.

    Safety rules (UNIQUE constraint: place_id, job_type, is_active):
    - Only ONE is_active=True row may exist per (place_id, job_type).
    - If an active job already exists for a place → skip that place entirely.
    - If multiple failed rows exist for the same place → keep only one,
      delete the rest before activating.
    - Wraps each activation in try/except to log and skip constraint conflicts.
    """
    from app.db.models.enrichment_job import EnrichmentJob
    from app.services.menu.orchestration.menu_job_scheduler import ensure_single_active_job
    from sqlalchemy import select
    from collections import defaultdict

    # Only reset network/cookie failures — not permanent parse failures
    retryable_errors = [
        "FETCH_FAIL",
        "COOKIES_INVALID",
        "FETCH_BLOCKED",
    ]

    all_failed = db.execute(
        select(EnrichmentJob)
        .where(EnrichmentJob.status == "failed")
        .where(EnrichmentJob.job_type == "menu")
        .order_by(EnrichmentJob.created_at.desc())
    ).scalars().all()

    retryable = [
        j for j in all_failed
        if any((j.last_error or "").startswith(e) for e in retryable_errors)
    ]

    _print(f"RESET: {len(all_failed)} failed jobs total, {len(retryable)} retryable")

    if dry_run:
        return len(retryable)

    # Build set of (place_id, job_type) that already have an is_active=True job
    retryable_place_ids = list({j.place_id for j in retryable if j.place_id})
    already_active = set(
        row.place_id
        for row in db.execute(
            select(EnrichmentJob.place_id)
            .where(EnrichmentJob.is_active.is_(True))
            .where(EnrichmentJob.job_type == "menu")
            .where(EnrichmentJob.place_id.in_(retryable_place_ids))
        ).all()
    )

    # Group retryable jobs by place_id (ordered newest-first already)
    by_place: dict = defaultdict(list)
    for job in retryable:
        by_place[job.place_id].append(job)

    now = _utcnow()
    activated = 0
    skipped_active = 0
    skipped_error = 0

    for place_id, jobs in by_place.items():
        if place_id in already_active:
            # This place already has an active job — don't create a second one
            skipped_active += 1
            logger.debug("reset_failed_jobs: skip place_id=%s already has active job", place_id)
            continue

        # Clean up: if multiple failed rows for the same place, delete extras.
        # The constraint allows only ONE is_active=False row per (place_id, job_type).
        # jobs is ordered newest-first; keep jobs[0], delete the rest.
        to_delete = jobs[1:]
        for stale in to_delete:
            try:
                db.delete(stale)
            except Exception as exc:
                logger.warning("reset_failed_jobs: delete stale failed id=%s error=%s", stale.id, exc)
        if to_delete:
            try:
                db.flush()
            except Exception as exc:
                db.rollback()
                logger.error("reset_failed_jobs: flush stale delete failed place_id=%s error=%s", place_id, exc)
                skipped_error += 1
                continue

        # Activate the surviving (newest) failed job
        job = jobs[0]
        try:
            job.status = "pending"
            job.is_active = True
            job.last_error = None
            job.locked_at = None
            job.locked_by = None
            job.updated_at = now
            db.flush()
            activated += 1
        except Exception as exc:
            db.rollback()
            logger.error(
                "reset_failed_jobs: UNIQUE conflict activating job id=%s place_id=%s error=%s",
                job.id, place_id, exc,
            )
            skipped_error += 1

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("reset_failed_jobs: commit failed error=%s", exc)
        return 0

    _print(
        f"RESET: activated={activated} "
        f"skipped_already_active={skipped_active} "
        f"skipped_error={skipped_error}"
    )
    return activated


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3: QUEUE MISSING JOBS
# ─────────────────────────────────────────────────────────────────────────────

def queue_missing_jobs(db, dry_run: bool = False) -> int:
    """
    Find places with grubhub_url but no active menu job, then enqueue them.
    """
    from app.db.models.place import Place
    from app.db.models.enrichment_job import EnrichmentJob
    from app.services.menu.orchestration.menu_job_scheduler import schedule_menu_jobs
    from sqlalchemy import select

    # Places that have a grubhub_url
    all_grubhub = db.execute(
        select(Place)
        .where(Place.grubhub_url.isnot(None))
        .where(Place.has_menu.is_(False))
        .where(Place.is_active.is_(True))
    ).scalars().all()

    # Which of those already have an active (pending/running) job?
    active_place_ids = set(
        db.execute(
            select(EnrichmentJob.place_id)
            .where(EnrichmentJob.job_type == "menu")
            .where(EnrichmentJob.is_active.is_(True))
            .where(EnrichmentJob.status.in_(["pending", "running"]))
        ).scalars().all()
    )

    to_queue = [p for p in all_grubhub if p.id not in active_place_ids]
    _print(f"QUEUE: {len(all_grubhub)} need menus, {len(active_place_ids)} already queued, {len(to_queue)} to enqueue")

    if dry_run or not to_queue:
        return len(to_queue)

    created = schedule_menu_jobs(db, to_queue, priority=1)
    db.commit()
    _print(f"QUEUE: {len(created)} new jobs created")
    return len(created)


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 4: RUN INGESTION LOOP
# ─────────────────────────────────────────────────────────────────────────────

def run_ingestion_loop(db, limit: Optional[int] = None, dry_run: bool = False) -> dict:
    """
    Process pending menu jobs in batches of BATCH_SIZE.
    Returns stats dict.
    """
    from app.db.models.enrichment_job import EnrichmentJob
    from app.services.menu.orchestration.menu_enrichment_worker import process_menu_job
    from sqlalchemy import select

    if dry_run:
        pending = db.execute(
            select(EnrichmentJob)
            .where(EnrichmentJob.job_type == "menu")
            .where(EnrichmentJob.is_active.is_(True))
            .where(EnrichmentJob.status == "pending")
        ).scalars().all()
        _print(f"INGEST: {len(pending)} pending jobs would be processed (dry-run)")
        return {"processed": 0, "succeeded": 0, "failed": 0, "cookie_error": False}

    stats = {"processed": 0, "succeeded": 0, "failed": 0, "cookie_error": False}
    batch_num = 0

    while batch_num < MAX_BATCHES:
        # Check remaining limit
        if limit is not None and stats["processed"] >= limit:
            _print(f"INGEST: limit={limit} reached, stopping")
            break

        batch_limit = BATCH_SIZE
        if limit is not None:
            batch_limit = min(BATCH_SIZE, limit - stats["processed"])

        # Fetch next batch of pending jobs
        jobs = db.execute(
            select(EnrichmentJob)
            .where(EnrichmentJob.job_type == "menu")
            .where(EnrichmentJob.is_active.is_(True))
            .where(EnrichmentJob.status == "pending")
            .order_by(EnrichmentJob.priority.desc(), EnrichmentJob.created_at.asc())
            .limit(batch_limit)
        ).scalars().all()

        if not jobs:
            _print("INGEST: no more pending jobs — queue empty")
            break

        batch_num += 1
        _print(f"INGEST: batch {batch_num}, processing {len(jobs)} jobs")

        for job in jobs:
            # Pre-mark as running
            now = _utcnow()
            job.status = "running"
            job.locked_at = now
            job.attempts = (job.attempts or 0) + 1
            job.last_attempted_at = now
            job.updated_at = now
            try:
                db.commit()
            except Exception:
                db.rollback()
                continue

            process_menu_job(db, job)
            db.expire(job)

            # Re-read result
            try:
                fresh = db.get(EnrichmentJob, job.id)
                status = fresh.status if fresh else "unknown"
                error = (fresh.last_error or "") if fresh else ""
            except Exception:
                status = "unknown"
                error = ""

            stats["processed"] += 1

            if status == "completed":
                stats["succeeded"] += 1
                _print(f"  OK  {job.place_id[:8]}...")
            else:
                stats["failed"] += 1
                if "COOKIES_INVALID" in error or "401" in error:
                    stats["cookie_error"] = True
                    _print(f"  FAIL {job.place_id[:8]}... — {error[:60]}")
                    _print("")
                    _print("  *** COOKIES EXPIRED — STOPPING BATCH ***")
                    _print("  Run: python backend/scripts/grab_grubhub_cookies.py")
                    _print("  Then: source backend/.grubhub_env && python backend/scripts/run_saturation.py")
                    return stats
                _print(f"  FAIL {job.place_id[:8]}... — {error[:60]}")

        # Progress summary after each batch
        _print_progress(db)

        if len(jobs) < batch_limit:
            _print("INGEST: last batch was smaller than limit — done")
            break

        if batch_num < MAX_BATCHES:
            time.sleep(SLEEP_BETWEEN_BATCHES)

    return stats


# ─────────────────────────────────────────────────────────────────────────────
# PROGRESS
# ─────────────────────────────────────────────────────────────────────────────

def _print_progress(db) -> None:
    from app.db.models.place import Place
    from app.db.models.enrichment_job import EnrichmentJob
    from sqlalchemy import select, func

    total = db.execute(select(func.count()).select_from(Place)).scalar_one()
    with_menu = db.execute(
        select(func.count()).select_from(Place).where(Place.has_menu.is_(True))
    ).scalar_one()
    with_grubhub = db.execute(
        select(func.count()).select_from(Place).where(Place.grubhub_url.isnot(None))
    ).scalar_one()
    pending = db.execute(
        select(func.count()).select_from(EnrichmentJob)
        .where(EnrichmentJob.status == "pending")
        .where(EnrichmentJob.job_type == "menu")
    ).scalar_one()
    failed = db.execute(
        select(func.count()).select_from(EnrichmentJob)
        .where(EnrichmentJob.status == "failed")
        .where(EnrichmentJob.job_type == "menu")
    ).scalar_one()

    success_rate = round(with_menu / with_grubhub * 100, 1) if with_grubhub else 0

    print(f"\n  TOTAL_PLACES      : {total}")
    print(f"  WITH_GRUBHUB_URL  : {with_grubhub}")
    print(f"  WITH_MENU         : {with_menu}")
    print(f"  PENDING_JOBS      : {pending}")
    print(f"  FAILED_JOBS       : {failed}")
    print(f"  SUCCESS_RATE      : {success_rate}%")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 5: URL DISCOVERY
# ─────────────────────────────────────────────────────────────────────────────

def run_url_discovery(db, limit: int = 200, dry_run: bool = False) -> dict:
    """
    Run Grubhub URL discovery for active places without grubhub_url.
    Uses discover_grubhub_urls.py functions directly.
    """
    from app.db.models.place import Place
    from sqlalchemy import select, func

    no_url_count = db.execute(
        select(func.count()).select_from(Place)
        .where(Place.is_active.is_(True))
        .where(Place.grubhub_url.is_(None))
    ).scalar_one()

    _print(f"DISCOVERY: {no_url_count} active places without grubhub_url")

    if dry_run:
        _print(f"DISCOVERY: would search up to {limit} places (dry-run)")
        return {"searched": 0, "matched": 0, "failed": 0}

    if no_url_count == 0:
        _print("DISCOVERY: all places have grubhub_url — skipping")
        return {"searched": 0, "matched": 0, "failed": 0}

    # Import functions from discover_grubhub_urls.py
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "discover_grubhub_urls",
            scripts_dir / "discover_grubhub_urls.py",
        )
        disc_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(disc_mod)
        _build_session = disc_mod._build_session
        search_grubhub = disc_mod.search_grubhub
        find_best_match = disc_mod.find_best_match
        build_grubhub_url = disc_mod.build_grubhub_url
    except Exception as exc:
        _print(f"DISCOVERY: could not load discover_grubhub_urls.py — {exc}")
        return {"searched": 0, "matched": 0, "failed": 0}

    places_to_search = db.execute(
        select(Place)
        .where(Place.is_active.is_(True))
        .where(Place.grubhub_url.is_(None))
        .where(Place.lat.isnot(None))
        .where(Place.lng.isnot(None))
        .order_by(Place.name.asc())
        .limit(limit)
    ).scalars().all()

    _print(f"DISCOVERY: searching {len(places_to_search)} places")

    try:
        session, headers = _build_session()
    except Exception as exc:
        _print(f"DISCOVERY: could not build session — {exc}")
        return {"searched": 0, "matched": 0, "failed": 0}

    stats = {"searched": 0, "matched": 0, "failed": 0}
    commit_every = 10

    for place in places_to_search:
        name = place.name or ""
        lat = place.lat
        lng = place.lng
        if not name or lat is None or lng is None:
            stats["failed"] += 1
            continue
        try:
            results = search_grubhub(session, headers, name, lat, lng)
            best = find_best_match(results, name, lat, lng) if results else None
            stats["searched"] += 1

            if best:
                url = build_grubhub_url(best)
                if url:
                    place.grubhub_url = url
                    db.add(place)
                    stats["matched"] += 1
                    _print(f"  MATCH {name[:40]:40s} → {url[:55]}")
                    if stats["matched"] % commit_every == 0:
                        db.commit()
            else:
                stats["failed"] += 1

            time.sleep(0.8)

        except SystemExit:
            # 401 from discover script — cookies expired
            _print("DISCOVERY: STOPPED — 401 from Grubhub (cookies expired)")
            break
        except Exception as exc:
            stats["failed"] += 1
            logger.debug("discovery_failed place=%s error=%s", name, exc)

    try:
        db.commit()
    except Exception:
        db.rollback()

    _print(f"DISCOVERY: searched={stats['searched']} matched={stats['matched']} no_match/fail={stats['failed']}")
    return stats


# ─────────────────────────────────────────────────────────────────────────────
# FINAL METRICS
# ─────────────────────────────────────────────────────────────────────────────

def print_final_metrics(db) -> None:
    from app.db.models.place import Place
    from app.db.models.enrichment_job import EnrichmentJob
    from app.db.models.place_claim import PlaceClaim
    from sqlalchemy import select, func

    total = db.execute(select(func.count()).select_from(Place)).scalar_one()
    active = db.execute(
        select(func.count()).select_from(Place).where(Place.is_active.is_(True))
    ).scalar_one()
    with_menu = db.execute(
        select(func.count()).select_from(Place).where(Place.has_menu.is_(True))
    ).scalar_one()
    with_grubhub = db.execute(
        select(func.count()).select_from(Place).where(Place.grubhub_url.isnot(None))
    ).scalar_one()
    no_menu_has_url = with_grubhub - with_menu

    completed_jobs = db.execute(
        select(func.count()).select_from(EnrichmentJob)
        .where(EnrichmentJob.status == "completed")
        .where(EnrichmentJob.job_type == "menu")
    ).scalar_one()
    failed_jobs = db.execute(
        select(func.count()).select_from(EnrichmentJob)
        .where(EnrichmentJob.status == "failed")
        .where(EnrichmentJob.job_type == "menu")
    ).scalar_one()
    pending_jobs = db.execute(
        select(func.count()).select_from(EnrichmentJob)
        .where(EnrichmentJob.status == "pending")
        .where(EnrichmentJob.job_type == "menu")
    ).scalar_one()

    total_claims = db.execute(select(func.count()).select_from(PlaceClaim)).scalar_one()

    success_rate = round(with_menu / with_grubhub * 100, 1) if with_grubhub else 0
    coverage = round(with_menu / active * 100, 1) if active else 0

    print("\n" + "=" * 70)
    print("  FINAL METRICS")
    print("=" * 70)
    print(f"  TOTAL_PLACES          : {total:,}")
    print(f"  ACTIVE_PLACES         : {active:,}")
    print(f"  WITH_GRUBHUB_URL      : {with_grubhub:,}")
    print(f"  WITH_MENU             : {with_menu:,} ({coverage}% of active)")
    print(f"  NO_MENU_HAS_URL       : {no_menu_has_url:,} (still retryable)")
    print(f"")
    print(f"  ENRICHMENT JOBS")
    print(f"    Completed           : {completed_jobs:,}")
    print(f"    Failed              : {failed_jobs:,}")
    print(f"    Pending             : {pending_jobs:,}")
    print(f"    Success rate        : {success_rate}%")
    print(f"")
    print(f"  TOTAL_CLAIMS          : {total_claims:,}")
    print("=" * 70)

    if pending_jobs > 0:
        print(f"\n  {pending_jobs} jobs still pending — re-run to continue")
    if failed_jobs > 0:
        print(f"  {failed_jobs} jobs failed — refresh cookies and re-run")
    if no_menu_has_url == 0 and pending_jobs == 0:
        print("\n  DATA COMPLETION COMPLETE — SYSTEM FULLY SATURATED AND PRODUCTION READY")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="CRAVE data saturation runner — maximizes menu coverage"
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Max places to ingest (default: unlimited)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show counts without making changes",
    )
    parser.add_argument(
        "--skip-discovery", action="store_true",
        help="Skip URL discovery phase",
    )
    parser.add_argument(
        "--skip-cookie-check", action="store_true",
        help="Skip cookie validation (use when you know cookies are set)",
    )
    parser.add_argument(
        "--reset-only", action="store_true",
        help="Only reset failed jobs and queue missing jobs, then exit",
    )
    args = parser.parse_args()

    print_banner()

    # Phase 1: Cookie validation
    if not args.dry_run and not args.skip_cookie_check:
        _print("Phase 1: Cookie validation")
        valid = validate_cookies()
        if not valid:
            sys.exit(1)
    else:
        _print("Phase 1: Cookie check skipped")

    from app.db.session import SessionLocal
    db = SessionLocal()

    try:
        # Phase 2: Reset failed jobs
        _print("\nPhase 2: Reset retryable failed jobs")
        reset_failed_jobs(db, dry_run=args.dry_run)

        # Phase 3: Queue missing jobs
        _print("\nPhase 3: Queue unscheduled places")
        queue_missing_jobs(db, dry_run=args.dry_run)

        if args.reset_only:
            _print("\n--reset-only: stopping after queue setup")
            print_final_metrics(db)
            return

        # Phase 4: Run ingestion loop
        _print(f"\nPhase 4: Menu ingestion loop (batch_size={BATCH_SIZE}, limit={args.limit or 'unlimited'})")
        ingest_stats = run_ingestion_loop(db, limit=args.limit, dry_run=args.dry_run)

        _print(f"\nIngestion complete: processed={ingest_stats['processed']} "
               f"succeeded={ingest_stats['succeeded']} failed={ingest_stats['failed']}")

        if ingest_stats.get("cookie_error"):
            _print("\n*** STOPPED: cookie expiry detected ***")
            _print("Run grab_grubhub_cookies.py then re-run this script")
            print_final_metrics(db)
            sys.exit(1)

        # Phase 5: URL Discovery (optional)
        if not args.skip_discovery:
            _print("\nPhase 5: Grubhub URL discovery")
            disc_stats = run_url_discovery(db, limit=200, dry_run=args.dry_run)
            if disc_stats["matched"] > 0:
                # Queue newly discovered URLs immediately
                _print("\nQueuing newly discovered places...")
                queue_missing_jobs(db, dry_run=args.dry_run)

        # Final metrics
        print_final_metrics(db)

    finally:
        db.close()


if __name__ == "__main__":
    main()
