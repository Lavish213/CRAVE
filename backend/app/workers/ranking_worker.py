from __future__ import annotations

import logging
import time
from contextlib import suppress

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.city import City
from app.services.ranking.city_ranking_worker import recompute_city_ranking


logger = logging.getLogger(__name__)

MAX_ERRORS = 20


def run_ranking_cycle(db: Session) -> None:
    """
    Runs a single ranking cycle across all active cities.

    Deterministic ordering:
        City.name ASC
        City.id ASC
    """

    stmt = (
        select(City)
        .where(City.is_active.is_(True))
        .order_by(
            City.name.asc(),
            City.id.asc(),
        )
    )

    cities = db.execute(stmt).scalars().all()

    for city in cities:
        logger.info("ranking_city_start city=%s", city.name)

        try:
            count = recompute_city_ranking(
                db=db,
                city_id=city.id,
            )
            logger.info("ranking_city_complete city=%s places=%s", city.name, count)

        except Exception as exc:
            logger.exception("ranking_city_failed city=%s error=%s", city.name, exc)


def run_worker(
    *,
    interval_seconds: int = 3600,
) -> None:
    """
    Long-running worker. Recomputes rankings periodically.
    Default interval: 1 hour.
    """
    logger.info("ranking_worker_start interval=%ss", interval_seconds)
    error_count = 0

    while True:
        db: Session = SessionLocal()
        try:
            run_ranking_cycle(db)
            logger.info("ranking_cycle_complete sleeping=%ss", interval_seconds)
            error_count = 0
        except Exception as exc:
            error_count += 1
            logger.exception("ranking_cycle_failed count=%s error=%s", error_count, exc)
            if error_count >= MAX_ERRORS:
                logger.critical("ranking_worker_stopping — too many errors")
                raise
        finally:
            with suppress(Exception):
                db.close()

        time.sleep(interval_seconds)


if __name__ == "__main__":
    run_worker()
