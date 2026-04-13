from __future__ import annotations
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.db.models.city import City
from app.db.session import SessionLocal
from app.services.discovery.discovery_service import ingest_candidate_v2


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


DEFAULT_SOURCE = "osm"
COMMIT_INTERVAL = 500


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _raw_dir() -> Path:
    return _project_root() / "data" / "raw"


# ---------------------------------------------------------
# File Loading
# ---------------------------------------------------------

def _load_places_file(city_slug: str) -> List[Dict[str, Any]]:
    path = _raw_dir() / f"{city_slug}_places.json"

    if not path.exists():
        raise FileNotFoundError(f"Normalized OSM file not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, list):
        raise ValueError("Expected list")

    return data


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        v = str(value).strip()
        return v or None
    except Exception:
        return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except Exception:
        return None


def _get_lat(raw: Dict[str, Any]) -> Optional[float]:
    return _safe_float(raw.get("lat"))


def _get_lng(raw: Dict[str, Any]) -> Optional[float]:
    return _safe_float(raw.get("lng") or raw.get("lon"))


def _get_category_hint(raw: Dict[str, Any]) -> Optional[str]:
    return (
        _clean(raw.get("category_hint"))
        or _clean(raw.get("amenity"))
        or _clean(raw.get("category"))
        or _clean(raw.get("shop"))
        or _clean(raw.get("tourism"))
        or _clean(raw.get("cuisine"))
    )


def _get_external_id(raw: Dict[str, Any]) -> Optional[str]:
    external_id = _clean(raw.get("external_id"))
    if external_id:
        return external_id

    osm_id = _clean(raw.get("osm_id"))
    osm_type = _clean(raw.get("osm_type"))

    if osm_id and osm_type:
        return f"osm:{osm_type}:{osm_id}"

    return None


# ---------------------------------------------------------
# City
# ---------------------------------------------------------

def _find_city(db: Session, slug: str) -> Optional[City]:
    return (
        db.query(City)
        .filter(City.slug == slug)
        .one_or_none()
    )


# ---------------------------------------------------------
# Pipeline (V2 UNIFIED)
# ---------------------------------------------------------

def promote_osm_places(city_slug: str) -> None:
    logger.info("osm_v2_start city=%s", city_slug)

    rows = _load_places_file(city_slug)
    logger.info("osm_rows_loaded=%s", len(rows))

    db = SessionLocal()

    try:
        city = _find_city(db, city_slug)

        if not city:
            raise RuntimeError(f"City not found: {city_slug}")

        processed = 0
        skipped = 0
        failed = 0

        for row in rows:
            try:
                name = _clean(row.get("name"))
                lat = _get_lat(row)
                lng = _get_lng(row)

                if not name or lat is None or lng is None:
                    skipped += 1
                    continue

                ingest_candidate_v2(
                    db=db,
                    name=name,
                    lat=lat,
                    lng=lng,
                    address=_clean(row.get("address")),
                    phone=_clean(row.get("phone")),
                    website=_clean(row.get("website")),
                    source=_clean(row.get("source")) or DEFAULT_SOURCE,
                    confidence=row.get("confidence"),
                    category_hint=_get_category_hint(row),
                    city_id=city.id,
                    external_id=_get_external_id(row),
                    raw_payload=row,
                )

                processed += 1

                if processed % COMMIT_INTERVAL == 0:
                    db.commit()
                    logger.info("osm_progress=%s", processed)

            except Exception as exc:
                failed += 1
                logger.debug("osm_row_failed error=%s", exc)

        db.commit()

        logger.info("osm_done processed=%s skipped=%s failed=%s", processed, skipped, failed)

    finally:
        db.close()

    logger.info("osm_v2_complete city=%s", city_slug)


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage:")
        print("python scripts/ingest/promote_osm_places.py <city_slug>")
        sys.exit(1)

    city = sys.argv[1].lower().strip()

    promote_osm_places(city)


if __name__ == "__main__":
    main()