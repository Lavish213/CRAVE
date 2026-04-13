from __future__ import annotations

import logging
from typing import List, Dict, Any

from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.services.menu.processing.menu_orchestrator import MenuOrchestrator


logger = logging.getLogger(__name__)


def ingest_menu_items(
    *,
    db: Session,
    place_id: str,
    items: List[Dict[str, Any]] | None = None,  # kept for compatibility
    force_refresh: bool = True,
) -> bool:
    """
    Modern ingestion entrypoint.

    Responsibilities:
    • Resolve place
    • Trigger orchestrator
    • Ensure pipeline consistency

    NOTE:
    • `items` is ignored (legacy compatibility)
    • All ingestion is now orchestrator-driven

    Returns:
        bool → success
    """

    # -----------------------------------------------------
    # VALIDATION
    # -----------------------------------------------------

    if not place_id:
        raise ValueError("MISSING_PLACE_ID")

    place: Place | None = (
        db.query(Place)
        .filter(Place.id == place_id)
        .one_or_none()
    )

    if not place:
        logger.error("menu_ingest_place_not_found place_id=%s", place_id)
        return False

    if not place.website:
        logger.warning(
            "menu_ingest_no_website place_id=%s",
            place_id,
        )
        return False

    # -----------------------------------------------------
    # EXECUTION
    # -----------------------------------------------------

    try:
        orchestrator = MenuOrchestrator()

        result = orchestrator.run_for_place(
            db=db,
            place=place,
            force_refresh=force_refresh,
        )

        success = bool(result.materialized)

        logger.info(
            "menu_ingest_complete place_id=%s success=%s sources=%s extracted=%s claims=%s",
            place_id,
            success,
            result.source_count,
            result.extracted_item_count,
            result.emitted_claim_count,
        )

        return success

    except Exception as exc:
        logger.exception(
            "menu_ingest_failed place_id=%s error=%s",
            place_id,
            exc,
        )
        return False