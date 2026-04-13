from __future__ import annotations

import logging
from typing import List

from app.db.session import SessionLocal
from app.db.models.place import Place

from app.services.menu.processing.menu_orchestrator import MenuOrchestrator

# 🔥 FETCHER (ONLY INPUT)
from app.services.menu.fetchers.grubhub_fetcher import fetch_grubhub_menu


logger = logging.getLogger(__name__)

BATCH_SIZE = 50


def run(limit: int = BATCH_SIZE):
    db = SessionLocal()

    try:
        places: List[Place] = (
            db.query(Place)
            .filter(Place.is_active.is_(True))
            .limit(limit)
            .all()
        )

        logger.info("menu_runner_places_found count=%s", len(places))

        orchestrator = MenuOrchestrator()

        success = 0
        failed = 0
        skipped = 0

        for place in places:
            try:
                # -------------------------------------------------
                # 🔥 STEP 1: FETCH
                # -------------------------------------------------
                payload = fetch_grubhub_menu(place)

                if not payload:
                    logger.debug("menu_runner_no_payload place_id=%s", place.id)
                    skipped += 1
                    continue

                # -------------------------------------------------
                # 🔥 STEP 2: ATTACH PAYLOAD TO PLACE
                # (orchestrator expects this)
                # -------------------------------------------------
                place.grubhub_payload = payload

                # -------------------------------------------------
                # 🔥 STEP 3: FULL PIPELINE (THIS IS THE SYSTEM)
                # -------------------------------------------------
                result = orchestrator.run_for_place(
                    db=db,
                    place=place,
                )

                if result.extracted_item_count == 0:
                    skipped += 1
                    continue

                logger.info(
                    "menu_runner_success place_id=%s extracted=%s claims=%s materialized=%s",
                    place.id,
                    result.extracted_item_count,
                    result.emitted_claim_count,
                    result.materialized,
                )

                success += 1

            except Exception as exc:
                failed += 1

                logger.exception(
                    "menu_runner_failed place_id=%s error=%s",
                    place.id,
                    exc,
                )

        logger.info(
            "menu_runner_complete success=%s failed=%s skipped=%s",
            success,
            failed,
            skipped,
        )

    finally:
        db.close()


if __name__ == "__main__":
    run()