from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.city import City
from app.services.discovery.discovery_service import ingest_candidate_v2


logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

SOURCE = "health"


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

def _project_root() -> Path:
    # scripts/ingest/promote_health_places.py → parents[2] = backend/
    return Path(__file__).resolve().parents[2]


def _raw_dir() -> Path:
    return _project_root() / "data" / "raw" / "health"


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except Exception:
        return None


# ---------------------------------------------------------
# File Loader
# ---------------------------------------------------------

def _load_checkpoint(city_slug: str) -> List[Dict[str, Any]]:
    path = _raw_dir() / f"{city_slug}_health_places.json"

    if not path.exists():
        raise FileNotFoundError(f"Health checkpoint not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Checkpoint must contain a list")

    return data


# ---------------------------------------------------------
# City Lookup
# ---------------------------------------------------------

def _find_city(db: Session, slug: str) -> Optional[City]:
    return (
        db.query(City)
        .filter(City.slug == slug)
        .one_or_none()
    )


# ---------------------------------------------------------
# Promotion (V2)
# ---------------------------------------------------------

def promote_health_places(city_slug: str) -> None:

    logger.info("health_v2_promotion_start city=%s", city_slug)

    rows = _load_checkpoint(city_slug)

    logger.info("health_rows_loaded count=%s", len(rows))

    db = SessionLocal()

    try:

        city = _find_city(db, city_slug)

        if not city:
            raise RuntimeError(f"City not found: {city_slug}")

        processed = 0
        failed = 0

        for row in rows:

            try:

                name = _clean(row.get("name"))
                lat = _safe_float(row.get("lat"))
                lng = _safe_float(row.get("lng"))

                if not name:
                    continue

                ingest_candidate_v2(
                    db=db,
                    name=name,
                    lat=lat,
                    lng=lng,
                    address=_clean(row.get("address")),
                    phone=_clean(row.get("phone")),
                    website=_clean(row.get("website")),
                    source=SOURCE,
                    confidence=row.get("confidence"),
                    category_hint=_clean(row.get("category_hint")),
                    city_id=city.id,
                    external_id=_clean(row.get("external_id")),
                    raw_payload=row.get("raw_payload") or row,
                )

                processed += 1

                if processed % 500 == 0:
                    db.commit()
                    logger.info("health_v2_progress processed=%s", processed)

            except Exception as exc:
                failed += 1
                logger.debug(
                    "health_v2_row_failed error=%s row=%s",
                    exc,
                    row,
                )

        db.commit()

        logger.info("health_v2_processed=%s", processed)
        logger.info("health_v2_failed=%s", failed)

    finally:
        db.close()

    logger.info("health_v2_promotion_complete city=%s", city_slug)