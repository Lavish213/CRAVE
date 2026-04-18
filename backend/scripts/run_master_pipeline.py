#!/usr/bin/env python3
"""
Master ingestion pipeline for CRAVE.

Phases:
  0  Baseline validation report
  1  Clean bad data (null coords, empty names) — soft cleanup
  2  OSM ingest for all cities
  3  Health dept ingest (Oakland ArcGIS — only configured city)
  4  Promote discovery candidates → places (unlimited)
  5  Intermediate validation
  6  Google Places ingest for configured cities (SF, Oakland, San Jose)
  7  Final promotion
  8  Final validation report

Usage:
    cd backend/
    python scripts/run_master_pipeline.py [--phases 0,2,4,8] [--skip-google]
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from typing import List, Optional, Set

# Ensure backend/ is on the path regardless of working directory.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("master_pipeline")


# ---------------------------------------------------------
# Phase 0/5/8 — Validation
# ---------------------------------------------------------

def phase_validation(label: str) -> dict:
    logger.info("=== VALIDATION: %s ===", label)
    try:
        from sqlalchemy import select, func
        from app.db.session import SessionLocal
        from app.db.models.place import Place
        from app.db.models.discovery_candidate import DiscoveryCandidate

        db = SessionLocal()
        try:
            total_places = db.execute(select(func.count()).select_from(Place)).scalar_one()
            active_places = db.execute(
                select(func.count()).select_from(Place).where(Place.is_active.is_(True))
            ).scalar_one()
            no_geo = db.execute(
                select(func.count()).select_from(Place)
                .where(Place.is_active.is_(True), Place.lat.is_(None))
            ).scalar_one()
            total_candidates = db.execute(
                select(func.count()).select_from(DiscoveryCandidate)
            ).scalar_one()
            pending_candidates = db.execute(
                select(func.count()).select_from(DiscoveryCandidate)
                .where(DiscoveryCandidate.status.in_(["raw", "candidate"]))
            ).scalar_one()
        finally:
            db.close()

        report = {
            "places_total": total_places,
            "places_active": active_places,
            "places_no_geo": no_geo,
            "candidates_total": total_candidates,
            "candidates_pending": pending_candidates,
        }
        for k, v in report.items():
            logger.info("  %s = %s", k, v)
        return report
    except Exception as exc:
        logger.error("validation_failed error=%s", exc)
        return {}


# ---------------------------------------------------------
# Phase 1 — Clean bad data
# ---------------------------------------------------------

def phase_clean() -> None:
    logger.info("=== PHASE 1: CLEAN BAD DATA ===")
    try:
        from sqlalchemy import update
        from app.db.session import SessionLocal
        from app.db.models.place import Place

        db = SessionLocal()
        try:
            # Soft-deactivate places with null lat/lng
            result = db.execute(
                update(Place)
                .where(Place.lat.is_(None), Place.is_active.is_(True))
                .values(is_active=False)
            )
            deactivated_no_geo = result.rowcount
            db.commit()
            logger.info("clean_deactivated_no_geo count=%s", deactivated_no_geo)

            # Soft-deactivate places with null/empty name
            result = db.execute(
                update(Place)
                .where(Place.name.is_(None), Place.is_active.is_(True))
                .values(is_active=False)
            )
            deactivated_no_name = result.rowcount
            db.commit()
            logger.info("clean_deactivated_no_name count=%s", deactivated_no_name)

        finally:
            db.close()
    except Exception as exc:
        logger.error("phase_clean_failed error=%s", exc)


# ---------------------------------------------------------
# Phase 2 — OSM ingest for all cities
# ---------------------------------------------------------

def phase_osm(city_slugs_filter: Optional[Set[str]] = None) -> None:
    logger.info("=== PHASE 2: OSM INGEST ===")
    try:
        from config.city_loader import load_cities_with_coords
        from ingest.sources.osm_fetch import fetch_osm_pois
        from app.db.session import SessionLocal
        from app.services.discovery.discovery_service import ingest_candidate_v2

        cities = load_cities_with_coords()
        logger.info("osm_cities_loaded count=%s", len(cities))

        if not cities:
            logger.warning("osm_no_cities_found")
            return

        total_inserted = 0
        total_failed = 0
        RADIUS = 0.065  # ~7km

        for city in cities:
            slug = city["slug"]
            if city_slugs_filter and slug not in city_slugs_filter:
                continue

            lat = city["lat"]
            lng = city["lng"]

            logger.info("osm_city_start city=%s lat=%s lng=%s", slug, lat, lng)

            try:
                records = fetch_osm_pois(
                    lat_min=lat - RADIUS,
                    lat_max=lat + RADIUS,
                    lon_min=lng - RADIUS,
                    lon_max=lng + RADIUS,
                )
                logger.info("osm_city_fetched city=%s count=%s", slug, len(records))

                db = SessionLocal()
                inserted = 0
                failed = 0
                try:
                    for rec in records:
                        try:
                            ingest_candidate_v2(
                                db=db,
                                name=rec.get("name"),
                                lat=rec.get("lat"),
                                lng=rec.get("lon"),  # OSM uses "lon"
                                address=rec.get("address"),
                                phone=rec.get("phone"),
                                website=rec.get("website"),
                                source="osm",
                                confidence=0.75,
                                category_hint=rec.get("category_hint"),
                                city_name=city["name"],
                                external_id=rec.get("external_id"),
                                raw_payload=rec.get("raw_payload"),
                            )
                            inserted += 1
                            if inserted % 500 == 0:
                                db.commit()
                                logger.info("osm_city_progress city=%s inserted=%s", slug, inserted)
                        except ValueError as e:
                            failed += 1
                            logger.debug("osm_row_skip city=%s reason=%s", slug, e)
                        except Exception as e:
                            failed += 1
                            logger.warning("osm_row_failed city=%s error=%s", slug, e)

                    db.commit()
                    logger.info("osm_city_done city=%s inserted=%s failed=%s", slug, inserted, failed)
                    total_inserted += inserted
                    total_failed += failed
                finally:
                    db.close()

            except Exception as exc:
                logger.exception("osm_city_exception city=%s error=%s", slug, exc)

            # Polite pause between cities
            time.sleep(2)

        logger.info("osm_phase_done total_inserted=%s total_failed=%s", total_inserted, total_failed)

    except Exception as exc:
        logger.exception("phase_osm_failed error=%s", exc)


# ---------------------------------------------------------
# Phase 3 — Health dept ingest (Oakland)
# ---------------------------------------------------------

def phase_health() -> None:
    logger.info("=== PHASE 3: HEALTH DEPT INGEST ===")
    try:
        from config.health_datasets import list_health_datasets
        from scripts.run_arcgis_ingest import run_arcgis_ingest

        datasets = list_health_datasets()
        logger.info("health_datasets_available datasets=%s", datasets)

        for city_slug in datasets:
            logger.info("health_city_start city=%s", city_slug)
            try:
                run_arcgis_ingest(city_slug)
                logger.info("health_city_done city=%s", city_slug)
            except Exception as exc:
                logger.exception("health_city_failed city=%s error=%s", city_slug, exc)

    except Exception as exc:
        logger.exception("phase_health_failed error=%s", exc)


# ---------------------------------------------------------
# Phase 4/7 — Promote candidates → places
# ---------------------------------------------------------

def phase_promote(limit: int = 5000) -> None:
    logger.info("=== PROMOTE CANDIDATES (limit=%s) ===", limit)
    try:
        from app.db.session import SessionLocal
        from app.services.discovery.pipeline_v2 import run_discovery_pipeline_v2

        db = SessionLocal()
        try:
            result = run_discovery_pipeline_v2(db=db, limit=limit)
            db.commit()
            logger.info("promote_done result=%s", result)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    except Exception as exc:
        logger.exception("phase_promote_failed error=%s", exc)


# ---------------------------------------------------------
# Phase 6 — Google Places ingest
# ---------------------------------------------------------

GOOGLE_CITIES = {
    "san_francisco": {
        "lat_min": 37.70, "lat_max": 37.83,
        "lon_min": -122.52, "lon_max": -122.35,
    },
    "oakland": {
        "lat_min": 37.70, "lat_max": 37.90,
        "lon_min": -122.35, "lon_max": -122.10,
    },
    "san_jose": {
        "lat_min": 37.20, "lat_max": 37.40,
        "lon_min": -121.98, "lon_max": -121.75,
    },
    "los_angeles": {
        "lat_min": 33.90, "lat_max": 34.15,
        "lon_min": -118.50, "lon_max": -118.15,
    },
    "san_diego": {
        "lat_min": 32.65, "lat_max": 32.85,
        "lon_min": -117.27, "lon_max": -117.05,
    },
}


def phase_google(api_key: str, city_slugs_filter: Optional[Set[str]] = None) -> None:
    logger.info("=== PHASE 6: GOOGLE PLACES INGEST ===")
    try:
        from app.db.session import SessionLocal
        from app.services.ingest.google_places_ingest import GooglePlacesIngest
        from app.services.discovery.discovery_service import ingest_candidate_v2

        total_inserted = 0

        for city_slug, bbox in GOOGLE_CITIES.items():
            if city_slugs_filter and city_slug not in city_slugs_filter:
                continue

            logger.info("google_city_start city=%s", city_slug)

            try:
                ingestor = GooglePlacesIngest(api_key=api_key)
                records = ingestor.scan_grid(
                    lat_min=bbox["lat_min"],
                    lat_max=bbox["lat_max"],
                    lon_min=bbox["lon_min"],
                    lon_max=bbox["lon_max"],
                    step_km=1.5,
                )
                logger.info("google_city_fetched city=%s count=%s", city_slug, len(records))

                db = SessionLocal()
                inserted = 0
                failed = 0
                try:
                    for rec in records:
                        try:
                            ingest_candidate_v2(
                                db=db,
                                name=rec.get("name"),
                                lat=rec.get("lat"),
                                lng=rec.get("lng") or rec.get("lon"),
                                address=rec.get("address"),
                                phone=rec.get("phone"),
                                website=rec.get("website"),
                                source="google_places",
                                confidence=rec.get("confidence", 0.85),
                                category_hint=rec.get("category_hint"),
                                city_slug=city_slug,
                                external_id=rec.get("external_id"),
                                raw_payload=rec,
                            )
                            inserted += 1
                            if inserted % 500 == 0:
                                db.commit()
                                logger.info("google_progress city=%s inserted=%s", city_slug, inserted)
                        except ValueError as e:
                            failed += 1
                            logger.debug("google_row_skip city=%s reason=%s", city_slug, e)
                        except Exception as e:
                            failed += 1
                            logger.warning("google_row_failed city=%s error=%s", city_slug, e)

                    db.commit()
                    logger.info("google_city_done city=%s inserted=%s failed=%s", city_slug, inserted, failed)
                    total_inserted += inserted
                finally:
                    db.close()

            except Exception as exc:
                logger.exception("google_city_exception city=%s error=%s", city_slug, exc)

        logger.info("google_phase_done total_inserted=%s", total_inserted)

    except Exception as exc:
        logger.exception("phase_google_failed error=%s", exc)


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def _parse_phases(phases_str: Optional[str]) -> Optional[Set[int]]:
    if not phases_str:
        return None
    return {int(p.strip()) for p in phases_str.split(",")}


def main() -> None:
    parser = argparse.ArgumentParser(description="CRAVE master ingestion pipeline")
    parser.add_argument(
        "--phases",
        default=None,
        help="Comma-separated phases to run (default: all). Example: 0,2,4,8",
    )
    parser.add_argument(
        "--skip-google",
        action="store_true",
        help="Skip Google Places ingest (phase 6)",
    )
    parser.add_argument(
        "--osm-cities",
        default=None,
        help="Comma-separated city slugs for OSM (default: all cities)",
    )
    parser.add_argument(
        "--google-cities",
        default=None,
        help="Comma-separated city slugs for Google (default: all configured)",
    )
    parser.add_argument(
        "--promote-limit",
        type=int,
        default=10000,
        help="Max candidates to promote per promotion phase (default: 10000)",
    )
    args = parser.parse_args()

    phases = _parse_phases(args.phases)
    osm_filter = set(args.osm_cities.split(",")) if args.osm_cities else None
    google_filter = set(args.google_cities.split(",")) if args.google_cities else None

    def should_run(phase: int) -> bool:
        return phases is None or phase in phases

    # --- Load Google API key ---
    google_api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "")

    start = time.time()
    logger.info("=== CRAVE MASTER PIPELINE START ===")

    if should_run(0):
        phase_validation("baseline")

    if should_run(1):
        phase_clean()

    if should_run(2):
        phase_osm(city_slugs_filter=osm_filter)

    if should_run(3):
        phase_health()

    if should_run(4):
        phase_promote(limit=args.promote_limit)

    if should_run(5):
        phase_validation("post-free-sources")

    if should_run(6) and not args.skip_google:
        if not google_api_key:
            logger.warning("google_api_key_missing — skipping phase 6")
        else:
            phase_google(api_key=google_api_key, city_slugs_filter=google_filter)

    if should_run(7):
        phase_promote(limit=args.promote_limit)

    if should_run(8):
        phase_validation("final")

    elapsed = round(time.time() - start, 2)
    logger.info("=== MASTER PIPELINE COMPLETE seconds=%s ===", elapsed)


if __name__ == "__main__":
    main()
