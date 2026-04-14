from __future__ import annotations

import logging
import time
from contextlib import suppress

from app.db.session import SessionLocal
from app.services.search.search_index_builder import build_search_index


logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 900   # rebuild index every 15 minutes
MAX_ERRORS = 20


def run_search_index_worker() -> None:
    logger.info("search_index_worker_start")
    error_count = 0

    while True:
        db = SessionLocal()
        try:
            count = build_search_index(db=db)
            logger.info("search_index_rebuilt places=%s", count)
            error_count = 0
        except Exception as exc:
            error_count += 1
            logger.exception("search_index_error count=%s error=%s", error_count, exc)
            if error_count >= MAX_ERRORS:
                logger.critical("search_index_worker_stopping — too many errors")
                raise
        finally:
            with suppress(Exception):
                db.close()

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    run_search_index_worker()
