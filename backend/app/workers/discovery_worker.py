from __future__ import annotations

import logging
import time
from contextlib import suppress

from app.db.session import SessionLocal
from app.services.discovery.pipeline_v2 import run_discovery_pipeline_v2


logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 120
BATCH_LIMIT = 50
MAX_ERRORS = 20


def run_discovery_worker() -> None:
    logger.info("discovery_worker_start")
    error_count = 0

    while True:
        db = SessionLocal()
        try:
            result = run_discovery_pipeline_v2(db=db, limit=BATCH_LIMIT)
            logger.info(
                "discovery_cycle_complete promoted=%s error=%s",
                result.get("promoted", 0),
                result.get("error"),
            )
            error_count = 0
        except Exception as exc:
            error_count += 1
            logger.exception("discovery_worker_error count=%s error=%s", error_count, exc)
            with suppress(Exception):
                db.rollback()
            if error_count >= MAX_ERRORS:
                logger.critical("discovery_worker_stopping — too many errors")
                raise
        finally:
            with suppress(Exception):
                db.close()

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    run_discovery_worker()
