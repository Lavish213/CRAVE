from __future__ import annotations

import logging
import time
from typing import List

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.place import Place
from app.db.models.place_truth import PlaceTruth

from app.services.menu.processing.menu_orchestrator import MenuOrchestrator
from app.services.scoring.recompute import recompute_place_scores


logger = logging.getLogger(__name__)


BATCH_SIZE = 25
MAX_PLACES_PER_RUN = 200
SLEEP_BETWEEN_BATCHES = 1.0

MENU_TRUTH_TYPE = "menu"


class MenuWorker:

    def __init__(self):
        self.orchestrator = MenuOrchestrator()

    def run(self):

        total_processed = 0
        error_count = 0

        while total_processed < MAX_PLACES_PER_RUN:

            db: Session = SessionLocal()

            try:

                places = self._load_places_requiring_menu(db)

                if not places:
                    logger.info("menu_worker_no_more_places")
                    break

                logger.info(
                    "menu_worker_batch_start batch_size=%s processed=%s",
                    len(places),
                    total_processed,
                )

                for place in places:

                    try:

                        result = self.orchestrator.run_for_place(
                            db=db,
                            place=place,
                        )

                        total_processed += 1
                        materialized = getattr(result, "materialized", False)

                        # Set has_menu flag and recompute score after successful materialization
                        if materialized:
                            place.has_menu = True
                            recompute_place_scores(db, places=[place])

                        logger.info(
                            "menu_worker_place_complete place_id=%s sources=%s extracted=%s claims=%s materialized=%s",
                            place.id,
                            getattr(result, "source_count", 0),
                            getattr(result, "extracted_item_count", 0),
                            getattr(result, "emitted_claim_count", 0),
                            materialized,
                        )

                        db.commit()

                    except Exception as exc:

                        db.rollback()
                        error_count += 1

                        logger.exception(
                            "menu_worker_place_failed place_id=%s error=%s",
                            place.id,
                            exc,
                        )

                    if total_processed >= MAX_PLACES_PER_RUN:
                        break

                logger.info(
                    "menu_worker_batch_complete processed=%s errors=%s",
                    total_processed,
                    error_count,
                )

            finally:
                db.close()

            time.sleep(SLEEP_BETWEEN_BATCHES)

        logger.info(
            "menu_worker_run_complete total_processed=%s errors=%s",
            total_processed,
            error_count,
        )

    def _load_places_requiring_menu(
        self,
        db: Session,
    ) -> List[Place]:

        query = (
            db.query(Place)
            .outerjoin(
                PlaceTruth,
                (PlaceTruth.place_id == Place.id)
                & (PlaceTruth.truth_type == MENU_TRUTH_TYPE),
            )
            .filter(
                Place.website.isnot(None),
                Place.website != "",
                PlaceTruth.id.is_(None),
            )
            .order_by(
                Place.rank_score.desc(),
                Place.id.asc(),
            )
            .limit(BATCH_SIZE)
        )

        places = query.all()

        logger.info(
            "menu_worker_places_loaded count=%s",
            len(places),
        )

        return places


def run_menu_worker():
    worker = MenuWorker()
    worker.run()