from __future__ import annotations

import logging
import math
from datetime import date
from typing import Dict, List

from sqlalchemy.orm import Session

from app.db.models.city import City
from app.services.discovery.discovery_service import ingest_candidate_v2
from app.services.discovery.overture_places import fetch_overture_places

logger = logging.getLogger(__name__)

# Same acquisition role as osm_ingest_job.py, different free source. Overture
# is bulk open data (no API key, no per-request billing), so like OSM it can
# run unattended on a schedule with no budget decision.

# Matches osm_ingest_job.py's BBOX_DEGREES — same reasoning (~8-9km box,
# imprecision/overlap across runs is harmless since ingest_candidate_v2
# upserts by external_id).
BBOX_DEGREES = 0.08

# Kept independent from OSM's MAX_CITIES_PER_RUN/rotation on purpose: this
# reads Parquet directly off S3 rather than hitting a shared rate-limited
# public API, so there's no "be gentle to a shared free service" constraint
# driving the cap the way there is for Overpass. Still bounded per run to
# keep each scheduled job fast and to spread S3 read cost over time rather
# than fetching every city in one run.
MAX_CITIES_PER_RUN = 5


def _rotation_offset(total: int, limit: int, today: date) -> int:
    """Same deterministic day-based rotation as osm_ingest_job.py, kept as
    its own copy rather than a shared import so each job's cadence can
    diverge independently later without coupling the two."""
    if total <= 0 or limit <= 0:
        return 0
    num_pages = max(1, math.ceil(total / limit))
    page = today.toordinal() % num_pages
    return page * limit


def _bbox_for_city(city: City) -> Dict[str, float]:
    return {
        "lat_min": city.lat - BBOX_DEGREES,
        "lat_max": city.lat + BBOX_DEGREES,
        "lon_min": city.lng - BBOX_DEGREES,
        "lon_max": city.lng + BBOX_DEGREES,
    }


def run_overture_city_ingest(
    *,
    db: Session,
    limit: int = MAX_CITIES_PER_RUN,
    today: date | None = None,
) -> dict:
    """
    Fetch nearby restaurants/cafes/bars/bakeries from Overture Maps' public
    Parquet data for a rotating slice of active cities and upsert them as
    DiscoveryCandidate rows (source="overture") via the same ingest path
    osm_ingest_job.py uses, so downstream promotion picks these up exactly
    like any other source.
    """
    if not limit or limit <= 0:
        return {"cities_scanned": 0, "fetched": 0, "ingested": 0, "errors": 0}

    total_cities = (
        db.query(City)
        .filter(City.is_active.is_(True))
        .filter(City.lat.is_not(None), City.lng.is_not(None))
        .count()
    )

    offset = _rotation_offset(total_cities, limit, today or date.today())

    cities: List[City] = (
        db.query(City)
        .filter(City.is_active.is_(True))
        .filter(City.lat.is_not(None), City.lng.is_not(None))
        .order_by(City.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    fetched = 0
    ingested = 0
    errors = 0

    for city in cities:
        bbox = _bbox_for_city(city)

        try:
            places = fetch_overture_places(**bbox)
        except Exception:
            logger.exception("overture_ingest_fetch_failed city_id=%s", city.id)
            errors += 1
            continue

        fetched += len(places)

        for place in places:
            try:
                ingest_candidate_v2(
                    db=db,
                    name=place.get("name"),
                    lat=place.get("lat"),
                    lng=place.get("lon"),
                    address=place.get("address"),
                    phone=place.get("phone"),
                    website=place.get("website"),
                    source=place.get("source") or "overture",
                    confidence=place.get("confidence"),
                    category_hint=place.get("category_hint"),
                    city_id=city.id,
                    external_id=place.get("external_id"),
                    raw_payload=place.get("raw_payload"),
                )
                db.commit()
                ingested += 1
            except Exception:
                db.rollback()
                logger.exception(
                    "overture_ingest_candidate_failed city_id=%s external_id=%s",
                    city.id,
                    place.get("external_id"),
                )
                errors += 1

    logger.info(
        "overture_city_ingest_complete cities_scanned=%s fetched=%s ingested=%s errors=%s",
        len(cities), fetched, ingested, errors,
    )

    return {
        "cities_scanned": len(cities),
        "fetched": fetched,
        "ingested": ingested,
        "errors": errors,
    }
