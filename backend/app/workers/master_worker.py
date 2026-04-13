from __future__ import annotations

import logging
import time

from app.services.workers.menu_worker import run_menu_worker
from app.services.ingest.google_places_ingest import run_google_ingest
from app.services.matching.place_matcher import match_place
from app.services.matching.place_writer import write_place_candidate_batch
from app.db.session import SessionLocal
from app.db.models.place import Place


logger = logging.getLogger(__name__)


# =========================================================
# CONFIG
# =========================================================

LOOP_DELAY_SECONDS = 10
INGEST_BATCH_LIMIT = 100


# =========================================================
# MASTER LOOP
# =========================================================

def run_master_worker():

    logger.info("master_worker_start")

    while True:

        db = SessionLocal()

        try:

            # -------------------------------------------------
            # STEP 1: INGEST (Google / AOI / Grid)
            # -------------------------------------------------

            logger.info("master_ingest_start")

            candidates = run_google_ingest(limit=INGEST_BATCH_LIMIT)

            logger.info(
                "master_ingest_complete count=%s",
                len(candidates or []),
            )

            # -------------------------------------------------
            # STEP 2: MATCH + WRITE
            # -------------------------------------------------

            if candidates:

                local_places = db.query(Place).all()

                write_batch = []

                for candidate in candidates:

                    result = match_place(
                        local_place=candidate,
                        provider_places=[
                            {
                                "name": p.name,
                                "lat": p.lat,
                                "lng": p.lng,
                                "id": p.id,
                            }
                            for p in local_places
                        ],
                    )

                    if not result.matched:
                        write_batch.append(candidate)

                if write_batch:
                    write_place_candidate_batch(db=db, candidates=write_batch)
                    db.commit()

                    logger.info(
                        "master_places_written count=%s",
                        len(write_batch),
                    )

            # -------------------------------------------------
            # STEP 3: MENU INGEST
            # -------------------------------------------------

            logger.info("master_menu_worker_start")

            run_menu_worker()

            logger.info("master_menu_worker_complete")

        except Exception as exc:

            db.rollback()

            logger.exception(
                "master_worker_error error=%s",
                exc,
            )

        finally:
            db.close()

        # -------------------------------------------------
        # LOOP DELAY
        # -------------------------------------------------

        logger.info(
            "master_worker_sleep seconds=%s",
            LOOP_DELAY_SECONDS,
        )

        time.sleep(LOOP_DELAY_SECONDS)