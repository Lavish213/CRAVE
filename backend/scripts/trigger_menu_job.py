#!/usr/bin/env python3
"""
trigger_menu_job.py
===================
Manually enqueue and immediately process a single Grubhub menu job.
Useful for testing the full pipeline for a specific place.

Usage
-----
    # By place_id (UUID):
    python backend/scripts/trigger_menu_job.py --place-id <uuid>

    # By Grubhub URL (finds or creates a temporary Place):
    python backend/scripts/trigger_menu_job.py --grubhub-url "https://www.grubhub.com/restaurant/..."

    # Fetch-only test (no DB required):
    python backend/scripts/trigger_menu_job.py --fetch-only --grubhub-url "https://www.grubhub.com/restaurant/..."

    # Verbose logging:
    python backend/scripts/trigger_menu_job.py --place-id <uuid> --verbose
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Load .grubhub_env if it exists (convenience for local dev)
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
    print(f"[ENV] Loaded {_env_file}", flush=True)


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def fetch_only(grubhub_url: str) -> None:
    """
    Run just the fetch stage — no DB needed.
    Prints payload summary if successful.
    """
    print(f"\n[FETCH ONLY] {grubhub_url}\n", flush=True)

    from app.services.menu.fetchers.grubhub_fetcher import fetch_grubhub_menu

    _url = grubhub_url

    class FakePlace:
        id = "test"
        grubhub_url = _url
        menu_source_url = None
        website = None
        lat = None
        lng = None

    payload = fetch_grubhub_menu(FakePlace())

    if payload is None:
        print("\nFETCH FAILED — payload is None", flush=True)
        sys.exit(1)

    print(f"\nFETCH SUCCESS — top-level keys: {list(payload.keys())[:15]}", flush=True)

    # Parse it too
    from app.services.menu.providers.grubhub_parser import parse_grubhub_payload
    items = parse_grubhub_payload(payload)
    print(f"PARSE: {len(items)} raw items", flush=True)

    if items:
        sample = items[0]
        print(f"Sample item: name={sample.get('item_name') or sample.get('name')} "
              f"section={sample.get('provider_category_name') or sample.get('menu_category_name')} "
              f"price={sample.get('base_price_cents')}", flush=True)

    # Adapt
    from app.services.menu.adapters.grubhub_adapter import adapt_grubhub_items
    extracted = adapt_grubhub_items(items)
    print(f"ADAPT: {len(extracted)} extracted items", flush=True)

    # Pipeline
    from app.services.menu.validation.validate_extracted_items import validate_extracted_items
    validated = validate_extracted_items(extracted)
    print(f"VALIDATE: {len(validated)} validated items", flush=True)

    from app.services.menu.menu_pipeline import process_extracted_menu
    canonical = process_extracted_menu(validated)
    print(f"PIPELINE: {canonical.item_count} canonical items in {len(canonical.sections)} sections", flush=True)

    if canonical.sections:
        for section in canonical.sections[:3]:
            print(f"  Section '{section.name}': {len(section.items)} items", flush=True)
            for item in section.items[:3]:
                print(f"    - {item.name} ${(item.price_cents or 0) / 100:.2f}", flush=True)

    print("\nFULL PIPELINE (no DB): OK", flush=True)


def run_full_job(place_id: str) -> None:
    """
    Enqueue a high-priority job for a place and process it immediately.
    """
    from app.db.session import SessionLocal
    from app.services.menu.orchestration.menu_job_scheduler import enqueue_menu_job
    from app.services.menu.orchestration.menu_enrichment_worker import process_menu_job
    from app.db.models.place import Place

    db = SessionLocal()
    try:
        place = db.query(Place).filter(Place.id == place_id).first()
        if not place:
            print(f"ERROR: place not found for id={place_id}", flush=True)
            sys.exit(1)

        print(f"\n[PLACE]\nid={place.id}\nname={getattr(place, 'name', '?')}\n"
              f"grubhub_url={getattr(place, 'grubhub_url', None)}\n"
              f"has_menu={getattr(place, 'has_menu', None)}", flush=True)

        job = enqueue_menu_job(db=db, place_id=place_id)
        if job is None:
            print("ERROR: enqueue_menu_job returned None", flush=True)
            sys.exit(1)

        print(f"\n[JOB ENQUEUED]\nid={job.id}\nstatus={job.status}\npriority={job.priority}", flush=True)

    except Exception as e:
        db.rollback()
        print(f"ERROR during enqueue: {e}", flush=True)
        db.close()
        sys.exit(1)
    finally:
        db.close()

    # Process in a fresh session (same as the loop does)
    job_db = SessionLocal()
    try:
        from app.db.models.enrichment_job import EnrichmentJob
        fresh_job = job_db.get(EnrichmentJob, job.id)
        if fresh_job is None:
            print(f"ERROR: job {job.id} disappeared", flush=True)
            sys.exit(1)

        print(f"\n[PROCESSING JOB {fresh_job.id}]", flush=True)
        process_menu_job(job_db, fresh_job)

        job_db.expire_all()
        result_job = job_db.get(EnrichmentJob, job.id)

        if result_job:
            print(f"\n[JOB RESULT]\nstatus={result_job.status}\nattempts={result_job.attempts}\n"
                  f"last_error={result_job.last_error}", flush=True)

            if result_job.status == "completed":
                print("\nSUCCESS — menu job completed!", flush=True)

                # Show materialized menu
                from app.services.menu.materialize_menu_truth import materialize_menu_truth
                menu = materialize_menu_truth(db=job_db, place_id=place_id)
                if menu:
                    print(f"Materialized: {menu.item_count} items in {len(menu.sections)} sections", flush=True)
            else:
                print(f"\nFAILED — status={result_job.status} error={result_job.last_error}", flush=True)
                sys.exit(1)
        else:
            print("WARNING: job not found after processing", flush=True)

    except Exception as e:
        job_db.rollback()
        print(f"ERROR during processing: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        job_db.close()


def find_place_by_grubhub_url(grubhub_url: str) -> str:
    """Find place_id by grubhub_url."""
    from app.db.session import SessionLocal
    from app.db.models.place import Place

    db = SessionLocal()
    try:
        place = (
            db.query(Place)
            .filter(Place.grubhub_url == grubhub_url)
            .first()
        )
        if place:
            return place.id

        # Also check menu_source_url
        place = (
            db.query(Place)
            .filter(Place.menu_source_url == grubhub_url)
            .first()
        )
        if place:
            return place.id

        print(f"ERROR: no place found with grubhub_url={grubhub_url}", flush=True)
        print("Tip: set grubhub_url on the place first, or use --place-id directly", flush=True)
        sys.exit(1)
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Trigger a single Grubhub menu enrichment job"
    )
    parser.add_argument("--place-id", help="Place UUID to process")
    parser.add_argument("--grubhub-url", help="Grubhub restaurant URL")
    parser.add_argument(
        "--fetch-only",
        action="store_true",
        help="Only test the fetch+parse pipeline, no DB required",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable DEBUG logging",
    )
    args = parser.parse_args()

    setup_logging(args.verbose)

    if not args.place_id and not args.grubhub_url:
        parser.print_help()
        sys.exit(1)

    if args.fetch_only:
        url = args.grubhub_url
        if not url:
            print("ERROR: --fetch-only requires --grubhub-url", flush=True)
            sys.exit(1)
        fetch_only(url)
        return

    place_id = args.place_id
    if not place_id:
        place_id = find_place_by_grubhub_url(args.grubhub_url)

    run_full_job(place_id)


if __name__ == "__main__":
    main()
