from __future__ import annotations

import logging
from typing import Dict, List

from sqlalchemy.orm import Session

from app.services.discovery.discovery_service import ingest_candidate_v2


logger = logging.getLogger(__name__)


def write_health_candidates(db: Session, records: List[Dict]) -> Dict[str, int]:
    inserted = 0
    skipped = 0
    failed = 0

    for record in records:
        name = record.get("name")
        if not name:
            skipped += 1
            continue

        lat = record.get("lat")
        lng = record.get("lng")

        if lat is None or lng is None:
            skipped += 1
            logger.debug("health_writer_skip_no_coords name=%s", name)
            continue

        try:
            ingest_candidate_v2(
                db=db,
                name=name,
                lat=lat,
                lng=lng,
                address=record.get("address"),
                city_name=record.get("city"),
                source=record.get("source", "health_dept"),
                confidence=record.get("confidence", 0.75),
                category_hint=record.get("category_hint"),
                external_id=record.get("external_id"),
                raw_payload=record.get("raw_payload"),
            )
            inserted += 1
        except ValueError as exc:
            logger.debug("health_writer_skip name=%s reason=%s", name, exc)
            skipped += 1
        except Exception as exc:
            logger.warning("health_writer_failed name=%s error=%s", name, exc)
            failed += 1

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("health_writer_commit_failed error=%s", exc)
        return {"inserted": 0, "skipped": skipped, "failed": failed + inserted}

    logger.info(
        "health_writer_complete inserted=%s skipped=%s failed=%s",
        inserted, skipped, failed,
    )

    return {"inserted": inserted, "skipped": skipped, "failed": failed}
