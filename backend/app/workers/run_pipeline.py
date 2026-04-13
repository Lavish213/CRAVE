from __future__ import annotations

import logging
import time
from contextlib import suppress

from app.services.workers.menu_worker import run_menu_worker
from app.services.ingest.master_ingest import run_master_ingest
from app.db.session import SessionLocal


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("pipeline_runner")


# =========================================================
# CONFIG
# =========================================================

MENU_INTERVAL_SECONDS = 60        # menu refresh loop
INGEST_INTERVAL_SECONDS = 300     # discovery loop
LOOP_SLEEP_SECONDS = 5            # base tick

# safety guard (prevents runaway loops)
MAX_LOOP_ERRORS = 25


# =========================================================
# SAFE DB CONTEXT
# =========================================================

def _run_ingest_safe():
    db = SessionLocal()
    try:
        run_master_ingest(db)
        logger.info("pipeline_ingest_complete")
    except Exception as exc:
        logger.exception("pipeline_ingest_failed error=%s", exc)
    finally:
        with suppress(Exception):
            db.close()


def _run_menu_safe():
    try:
        run_menu_worker()
        logger.info("pipeline_menu_complete")
    except Exception as exc:
        logger.exception("pipeline_menu_failed error=%s", exc)


# =========================================================
# MAIN LOOP
# =========================================================

def run_loop():
    last_menu_run = 0.0
    last_ingest_run = 0.0
    error_count = 0

    logger.info("pipeline_runner_started")

    while True:
        now = time.time()

        try:
            # -------------------------------------------------
            # INGEST LOOP (places creation / matching)
            # -------------------------------------------------
            if now - last_ingest_run >= INGEST_INTERVAL_SECONDS:
                logger.info("pipeline_ingest_start")
                _run_ingest_safe()
                last_ingest_run = now

            # -------------------------------------------------
            # MENU LOOP (menu extraction + truth)
            # -------------------------------------------------
            if now - last_menu_run >= MENU_INTERVAL_SECONDS:
                logger.info("pipeline_menu_start")
                _run_menu_safe()
                last_menu_run = now

            error_count = 0  # reset on success

        except Exception as loop_error:
            error_count += 1

            logger.exception(
                "pipeline_loop_error count=%s error=%s",
                error_count,
                loop_error,
            )

            # 🔥 HARD SAFETY: stop if something is fundamentally broken
            if error_count >= MAX_LOOP_ERRORS:
                logger.critical("pipeline_stopping_too_many_errors")
                raise

        time.sleep(LOOP_SLEEP_SECONDS)


# =========================================================
# ENTRYPOINT
# =========================================================

if __name__ == "__main__":
    run_loop()