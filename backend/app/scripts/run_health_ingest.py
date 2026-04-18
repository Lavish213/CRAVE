from __future__ import annotations

import argparse
import logging
import sys

from app.db.session import SessionLocal
from app.services.discovery.health_connector import HealthConnector
from app.services.discovery.health_parser import parse_records
from app.services.discovery.health_normalizer import normalize_records
from app.services.discovery.health_geocoder import geocode_records
from app.services.discovery.health_writer import write_health_candidates


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("health_ingest")


def run(source: str, record_key: str = None) -> None:
    connector = HealthConnector()

    logger.info("health_ingest_start source=%s", source)

    if source.startswith("http://") or source.startswith("https://"):
        if source.endswith(".json"):
            raw = connector.fetch_json(source, record_key=record_key)
        else:
            raw = connector.fetch_csv(source)
    else:
        raw = connector.load_file(source)

    if not raw:
        logger.warning("health_ingest_no_raw_records source=%s", source)
        return

    logger.info("health_ingest_raw_count count=%s", len(raw))

    parsed = parse_records(raw)
    logger.info("health_ingest_parsed_count count=%s", len(parsed))

    normalized = normalize_records(parsed)
    logger.info("health_ingest_normalized_count count=%s", len(normalized))

    geocoded = geocode_records(normalized)
    with_coords = sum(1 for r in geocoded if r.get("lat") and r.get("lng"))
    logger.info("health_ingest_geocoded_count total=%s with_coords=%s", len(geocoded), with_coords)

    db = SessionLocal()
    try:
        result = write_health_candidates(db, geocoded)
        logger.info(
            "health_ingest_complete inserted=%s skipped=%s failed=%s",
            result["inserted"],
            result["skipped"],
            result["failed"],
        )
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Health department ingest")
    parser.add_argument("source", help="CSV/JSON URL or local file path")
    parser.add_argument("--record-key", default=None, help="JSON key containing record array")
    args = parser.parse_args()

    try:
        run(source=args.source, record_key=args.record_key)
    except Exception as exc:
        logger.error("health_ingest_fatal error=%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
