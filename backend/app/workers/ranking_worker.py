from __future__ import annotations

import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.city import City
from app.services.ranking.city_ranking_worker import recompute_city_ranking


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


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
        logger.info(f"Recomputing ranking for city: {city.name}")

        try:
            count = recompute_city_ranking(
                db=db,
                city_id=city.id,
            )

            logger.info(
                f"City {city.name} ranking updated "
                f"({count} places)"
            )

        except Exception as e:
            logger.exception(
                f"Ranking failed for city {city.name}: {e}"
            )


def run_worker(
    *,
    interval_seconds: int = 3600,
) -> None:
    """
    Long-running worker.

    Recomputes rankings periodically.

    Default interval:
        1 hour
    """

    logger.info("Ranking worker started")

    while True:

        db: Session = SessionLocal()

        try:
            run_ranking_cycle(db)

        finally:
            db.close()

        logger.info(
            f"Ranking cycle complete, sleeping "
            f"{interval_seconds}s"
        )

        time.sleep(interval_seconds)


if __name__ == "__main__":
    run_worker()