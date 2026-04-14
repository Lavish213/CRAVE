from __future__ import annotations

import logging
import time
from contextlib import suppress

from sqlalchemy import select

from app.db.session import SessionLocal
from app.db.models.place import Place
from app.services.truth.truth_resolver_v2 import resolve_place_truths_v2


logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 600       # rebuild truths every 10 minutes
BATCH_SIZE = 100
MAX_ERRORS = 20


def run_truth_rebuild_cycle(db) -> int:
    """Rebuild truths for all active places. Returns count of places processed."""
    stmt = (
        select(Place)
        .where(Place.is_active.is_(True))
        .order_by(Place.id.asc())
        .limit(BATCH_SIZE)
    )
    places = list(db.execute(stmt).scalars().all())

    rebuilt = 0
    for place in places:
        try:
            truths = resolve_place_truths_v2(db=db, place_id=place.id)
            if truths:
                db.commit()
                rebuilt += 1
        except Exception as exc:
            logger.warning("truth_rebuild_place_failed place_id=%s error=%s", place.id, exc)
            with suppress(Exception):
                db.rollback()

    return rebuilt


def run_truth_rebuild_worker() -> None:
    logger.info("truth_rebuild_worker_start")
    error_count = 0

    while True:
        db = SessionLocal()
        try:
            count = run_truth_rebuild_cycle(db)
            logger.info("truth_rebuild_cycle_complete rebuilt=%s", count)
            error_count = 0
        except Exception as exc:
            error_count += 1
            logger.exception("truth_rebuild_error count=%s error=%s", error_count, exc)
            if error_count >= MAX_ERRORS:
                logger.critical("truth_rebuild_worker_stopping — too many errors")
                raise
        finally:
            with suppress(Exception):
                db.close()

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    run_truth_rebuild_worker()
