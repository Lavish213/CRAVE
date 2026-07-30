from __future__ import annotations

import logging
import math
from datetime import date
from typing import Dict, List

from sqlalchemy.orm import Session

from app.db.models.city import City
from app.services.discovery.discovery_service import ingest_candidate_v2
from app.services.discovery.osm_overpass import fetch_osm_pois

logger = logging.getLogger(__name__)

# Nothing scheduled ever fetched new candidates from the outside world —
# the scheduled "discovery" job (see app/scheduler.py::_job_discovery) only
# promotes candidates already sitting in discovery_candidates; nothing
# refilled that queue. OSM/Overpass is free (no API key, no billing), so
# unlike Google Places it can be scheduled unattended without a budget
# decision. This module is the acquisition half that was missing.

# ~0.08 degrees is roughly an 8-9km box at US latitudes — wide enough to
# cover a city's core in one Overpass query without one call per
# neighborhood. Overpass bbox queries don't need to be precise, and
# overlap across nightly runs is harmless: ingest_candidate_v2 upserts by
# external_id (osm:<type>:<id>), so re-fetching the same POI is a no-op.
BBOX_DEGREES = 0.08

# Keep each run small and bounded — this runs against the free public
# Overpass instance (overpass-api.de), which asks callers to be gentle.
# Per-request throttling to that domain is already enforced generically by
# app.services.network.http_fetcher (used internally by fetch_osm_pois),
# the same mechanism already relied on for Nominatim's rate policy.
MAX_CITIES_PER_RUN = 5


def _rotation_offset(total: int, limit: int, today: date) -> int:
    """
    Deterministic day-based rotation so every active city eventually gets
    scanned instead of only ever scanning the same first `limit` cities
    (ordered by id) forever. Avoids needing a new "last scanned" column /
    migration just to spread coverage across cities.
    """
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


def run_osm_city_ingest(
    *,
    db: Session,
    limit: int = MAX_CITIES_PER_RUN,
    today: date | None = None,
) -> dict:
    """
    Fetch nearby restaurants/cafes/bars/bakeries from the public Overpass
    API for a rotating slice of active cities and upsert them as
    DiscoveryCandidate rows (source="osm") via the same ingest path the
    manual scripts use (app.services.discovery.discovery_service.
    ingest_candidate_v2), so downstream promotion picks these up exactly
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
            pois = fetch_osm_pois(**bbox)
        except Exception:
            logger.exception("osm_ingest_fetch_failed city_id=%s", city.id)
            errors += 1
            continue

        fetched += len(pois)

        for poi in pois:
            try:
                ingest_candidate_v2(
                    db=db,
                    name=poi.get("name"),
                    lat=poi.get("lat"),
                    lng=poi.get("lon"),
                    address=poi.get("address"),
                    phone=poi.get("phone"),
                    website=poi.get("website"),
                    source=poi.get("source") or "osm",
                    confidence=poi.get("confidence"),
                    category_hint=poi.get("category_hint"),
                    city_id=city.id,
                    external_id=poi.get("external_id"),
                    raw_payload=poi.get("raw_payload"),
                )
                db.commit()
                ingested += 1
            except Exception:
                db.rollback()
                logger.exception(
                    "osm_ingest_candidate_failed city_id=%s external_id=%s",
                    city.id,
                    poi.get("external_id"),
                )
                errors += 1

    logger.info(
        "osm_city_ingest_complete cities_scanned=%s fetched=%s ingested=%s errors=%s",
        len(cities), fetched, ingested, errors,
    )

    return {
        "cities_scanned": len(cities),
        "fetched": fetched,
        "ingested": ingested,
        "errors": errors,
    }
