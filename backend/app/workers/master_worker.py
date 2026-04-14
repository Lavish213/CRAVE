from __future__ import annotations

import logging
import time
from contextlib import suppress

from app.db.session import SessionLocal
from app.services.discovery.pipeline_v2 import run_discovery_pipeline_v2
from app.services.workers.menu_worker import run_menu_worker
from app.services.scoring.recompute import recompute_place_scores
from app.db.models.place import Place


logger = logging.getLogger(__name__)


# =========================================================
# CONFIG
# =========================================================

LOOP_DELAY_SECONDS    = 30
DISCOVERY_BATCH_LIMIT = 50
MAX_LOOP_ERRORS       = 20


# =========================================================
# SAFE RUNNERS
# =========================================================

def _run_recompute_safe(db) -> None:
    """Recompute scores for all unscored or stale places (rank_score=0 or last_scored_at IS NULL)."""
    try:
        from sqlalchemy import or_
        places = (
            db.query(Place)
            .filter(Place.is_active.is_(True))
            .filter(
                or_(Place.rank_score == 0, Place.last_scored_at.is_(None))
            )
            .limit(500)
            .all()
        )
        if places:
            updated = recompute_place_scores(db, places=places)
            db.commit()
            logger.info("master_recompute_complete updated=%s", updated)
    except Exception as exc:
        logger.exception("master_recompute_failed error=%s", exc)
        with suppress(Exception):
            db.rollback()


def _run_discovery_safe(db) -> None:
    try:
        result = run_discovery_pipeline_v2(db=db, limit=DISCOVERY_BATCH_LIMIT)
        logger.info("master_discovery_complete promoted=%s", result.get("promoted", 0))
    except Exception as exc:
        logger.exception("master_discovery_failed error=%s", exc)
        with suppress(Exception):
            db.rollback()


def _run_menu_safe() -> None:
    try:
        run_menu_worker()
        logger.info("master_menu_complete")
    except Exception as exc:
        logger.exception("master_menu_failed error=%s", exc)


def _run_images_safe(db) -> None:
    try:
        from app.workers.image_worker import ImageWorker
        worker = ImageWorker()
        result = worker.run(db=db, limit=30)
        logger.info(
            "master_images_complete processed=%s images_written=%s",
            result.get("processed", 0),
            result.get("images_written", 0),
        )
    except Exception as exc:
        logger.exception("master_images_failed error=%s", exc)
        with suppress(Exception):
            db.rollback()


# =========================================================
# MASTER LOOP
# =========================================================

def run_master_worker() -> None:
    logger.info("master_worker_start")
    error_count = 0

    while True:
        db = SessionLocal()
        try:
            # Stage 1: discover + promote candidates → places
            _run_discovery_safe(db)

            # Stage 1b: score any newly promoted places (rank_score=0)
            _run_recompute_safe(db)

            # Stage 2: menu ingestion for known places
            _run_menu_safe()

            # Stage 3: image crawling for known places
            _run_images_safe(db)

            error_count = 0

        except Exception as exc:
            error_count += 1
            logger.exception("master_worker_loop_error count=%s error=%s", error_count, exc)
            with suppress(Exception):
                db.rollback()
            if error_count >= MAX_LOOP_ERRORS:
                logger.critical("master_worker_stopping — too many errors")
                raise

        finally:
            with suppress(Exception):
                db.close()

        logger.info("master_worker_sleep seconds=%s", LOOP_DELAY_SECONDS)
        time.sleep(LOOP_DELAY_SECONDS)


if __name__ == "__main__":
    run_master_worker()
