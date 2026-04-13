# FILE: backend/app/services/menu/menu_trigger.py

from __future__ import annotations

import logging
import time
from typing import Optional, List

from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.services.menu.processing.menu_orchestrator import MenuOrchestrator


logger = logging.getLogger(__name__)


BATCH_SIZE = 25
MAX_BATCH_SIZE = 100
MAX_TOTAL_RUNTIME = 30.0
PER_PLACE_TIMEOUT = 8.0


def _clamp_limit(limit: int) -> int:
    try:
        n = int(limit)
    except Exception:
        return BATCH_SIZE
    return max(1, min(MAX_BATCH_SIZE, n))


def _clean_str(val: Optional[str]) -> Optional[str]:
    if not val:
        return None
    try:
        v = str(val).strip()
        return v or None
    except Exception:
        return None


def run_menu_trigger(
    *,
    db: Session,
    city_id: Optional[str] = None,
    limit: int = BATCH_SIZE,
    force_refresh: bool = False,
) -> int:
    limit = _clamp_limit(limit)
    city_id = _clean_str(city_id)

    start_time = time.monotonic()

    try:
        query = db.query(Place).filter(
            Place.is_active.is_(True),
            Place.website.isnot(None),
        )

        if city_id:
            query = query.filter(Place.city_id == city_id)

        places: List[Place] = (
            query.order_by(
                Place.rank_score.desc(),
                Place.id.asc(),
            )
            .limit(limit)
            .all()
        )

    except Exception as exc:
        logger.exception("menu_trigger_query_failed error=%s", exc)
        return 0

    if not places:
        logger.info("menu_trigger_no_places city_id=%s", city_id)
        return 0

    orchestrator = MenuOrchestrator()

    processed = 0
    failed = 0
    skipped = 0

    logger.info(
        "menu_trigger_start total=%s city_id=%s limit=%s",
        len(places),
        city_id,
        limit,
    )

    for place in places:

        if time.monotonic() - start_time > MAX_TOTAL_RUNTIME:
            logger.warning(
                "menu_trigger_timeout total_runtime_exceeded processed=%s failed=%s skipped=%s",
                processed,
                failed,
                skipped,
            )
            break

        place_id = getattr(place, "id", None)
        website = _clean_str(getattr(place, "website", None))

        if not place_id or not website:
            skipped += 1
            continue

        place_start = time.monotonic()

        try:
            result = orchestrator.run_for_place(
                db=db,
                place=place,
                force_refresh=force_refresh,
            )

            duration = round(time.monotonic() - place_start, 3)

            if duration > PER_PLACE_TIMEOUT:
                logger.warning(
                    "menu_trigger_slow_place place_id=%s duration=%ss",
                    place_id,
                    duration,
                )

            processed += 1

            logger.info(
                "menu_trigger_place_done place_id=%s sources=%s fetched=%s items=%s claims=%s materialized=%s t=%ss",
                place_id,
                getattr(result, "source_count", None),
                getattr(result, "fetched_count", None),
                getattr(result, "extracted_item_count", None),
                getattr(result, "emitted_claim_count", None),
                getattr(result, "materialized", None),
                duration,
            )

        except Exception as exc:
            failed += 1

            logger.warning(
                "menu_trigger_place_failed place_id=%s error=%s",
                place_id,
                exc,
            )

            continue

    total_time = round(time.monotonic() - start_time, 3)

    logger.info(
        "menu_trigger_complete processed=%s failed=%s skipped=%s total=%s runtime=%ss",
        processed,
        failed,
        skipped,
        len(places),
        total_time,
    )

    return processed