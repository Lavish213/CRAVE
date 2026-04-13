from __future__ import annotations

import logging
import sys
from typing import Dict, List

from app.db.session import SessionLocal
from app.services.discovery.discovery_service import ingest_candidate_v2
from app.services.discovery.pipeline_v2 import run_discovery_pipeline_v2

from app.services.ingest.google_places_ingest import GooglePlacesIngest

# ✅ NEW
from app.services.ingest.grubhub_ingest import ingest_grubhub_payload


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# =========================================================
# CONFIG
# =========================================================

CITY_BBOX: Dict[str, Dict[str, float]] = {
    "oakland": {
        "lat_min": 37.70,
        "lat_max": 37.90,
        "lon_min": -122.35,
        "lon_max": -122.10,
    },
    "san_francisco": {
        "lat_min": 37.70,
        "lat_max": 37.83,
        "lon_min": -122.52,
        "lon_max": -122.35,
    },
    "san_jose": {
        "lat_min": 37.20,
        "lat_max": 37.40,
        "lon_min": -121.98,
        "lon_max": -121.75,
    },
}

CITY_ALIASES: Dict[str, str] = {
    "san-francisco": "san_francisco",
    "san francisco": "san_francisco",
    "san-jose": "san_jose",
    "san jose": "san_jose",
}

DEFAULT_STEP_KM = 1.5
DEFAULT_PROMOTION_LIMIT = 500


# =========================================================
# HELPERS
# =========================================================

def _clean(value: object) -> str | None:
    if value is None:
        return None
    try:
        cleaned = str(value).strip()
        return cleaned or None
    except Exception:
        return None


def _canonical_city_slug(city_slug: str) -> str:
    city_slug = city_slug.strip().lower()
    return CITY_ALIASES.get(city_slug, city_slug)


def _dedupe_records(records: List[dict]) -> List[dict]:
    seen: set[str] = set()
    out: List[dict] = []

    for record in records:
        external_id = _clean(record.get("external_id"))
        name = _clean(record.get("name"))
        lat = record.get("lat")
        lng = record.get("lng") if record.get("lng") is not None else record.get("lon")

        if external_id:
            key = f"id:{external_id}"
        elif name and lat is not None and lng is not None:
            key = f"synthetic:{name.lower()}:{round(float(lat), 6)}:{round(float(lng), 6)}"
        else:
            continue

        if key in seen:
            continue

        seen.add(key)
        out.append(record)

    return out


# =========================================================
# GOOGLE INGEST
# =========================================================

def run_google_ingest(
    *,
    db,
    city_slug: str,
    api_key: str,
    step_km: float,
) -> int:

    bbox = CITY_BBOX[city_slug]

    ingestor = GooglePlacesIngest(api_key=api_key)

    raw_records = ingestor.scan_grid(
        lat_min=bbox["lat_min"],
        lat_max=bbox["lat_max"],
        lon_min=bbox["lon_min"],
        lon_max=bbox["lon_max"],
        step_km=step_km,
    )

    records = _dedupe_records(raw_records)

    inserted = 0

    for record in records:
        try:
            ingest_candidate_v2(
                db=db,
                name=record.get("name"),
                lat=record.get("lat"),
                lng=record.get("lng") if record.get("lng") is not None else record.get("lon"),
                address=record.get("address"),
                phone=record.get("phone"),
                website=record.get("website"),
                source="google_places",
                confidence=record.get("confidence", 0.72),
                category_hint="restaurant",
                city_slug=city_slug,
                external_id=record.get("external_id"),
                raw_payload=record,
            )
            inserted += 1
        except Exception as exc:
            logger.warning("google_candidate_failed error=%s", exc)

    return inserted


# =========================================================
# MAIN PIPELINE
# =========================================================

def run_full_ingest(
    *,
    city_slug: str,
    google_api_key: str,
    grubhub_payloads: List[dict],
    step_km: float = DEFAULT_STEP_KM,
    promotion_limit: int = DEFAULT_PROMOTION_LIMIT,
) -> None:

    city_slug = _canonical_city_slug(city_slug)

    if city_slug not in CITY_BBOX:
        raise RuntimeError(f"Invalid city: {city_slug}")

    db = SessionLocal()

    try:

        logger.info("INGEST START city=%s", city_slug)

        # -----------------------------------------
        # 1. GOOGLE
        # -----------------------------------------
        google_count = run_google_ingest(
            db=db,
            city_slug=city_slug,
            api_key=google_api_key,
            step_km=step_km,
        )

        logger.info("google_ingested=%s", google_count)

        # -----------------------------------------
        # 2. GRUBHUB
        # -----------------------------------------
        grubhub_total = 0

        for payload in grubhub_payloads:
            count = ingest_grubhub_payload(
                payload=payload,
                city_id=city_slug,
            )
            grubhub_total += count

        logger.info("grubhub_ingested=%s", grubhub_total)

        db.commit()

        # -----------------------------------------
        # 3. PROMOTION PIPELINE
        # -----------------------------------------
        result = run_discovery_pipeline_v2(
            db=db,
            limit=promotion_limit,
        )

        db.commit()

        logger.info(
            "promotion_done promoted=%s error=%s",
            result.get("promoted"),
            result.get("error"),
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# =========================================================
# CLI
# =========================================================

def main():
    if len(sys.argv) < 3:
        print("Usage:")
        print("python run_ingest_pipeline.py <city_slug> <google_api_key>")
        sys.exit(1)

    city_slug = sys.argv[1]
    api_key = sys.argv[2]

    # ⚠️ TEMP: empty grubhub payloads until wired
    grubhub_payloads: List[dict] = []

    run_full_ingest(
        city_slug=city_slug,
        google_api_key=api_key,
        grubhub_payloads=grubhub_payloads,
    )


if __name__ == "__main__":
    main()