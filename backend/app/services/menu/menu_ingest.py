from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.services.menu.processing.menu_orchestrator import MenuOrchestrator


logger = logging.getLogger(__name__)


def ingest_menu_items(
    *,
    db: Session,
    place_id: str,
    items=None,           # legacy compat — ignored, orchestrator handles sourcing
    force_refresh: bool = True,  # legacy compat — ignored
) -> bool:
    """
    Modern ingestion entrypoint. Resolves place and triggers MenuOrchestrator.

    NOTE: `items` and `force_refresh` are kept for call-site compatibility but
    are no longer used. All extraction is orchestrator-driven.

    Returns:
        bool → True if menu was successfully materialized
    """
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

    if not place.website and not place.menu_source_url and not place.grubhub_url:
        logger.warning("menu_ingest_no_source place_id=%s", place_id)
        return False

    try:
        orchestrator = MenuOrchestrator()

        # run_for_place signature: (self, *, db, place) — no extra kwargs
        result = orchestrator.run_for_place(db=db, place=place)

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
        logger.exception("menu_ingest_failed place_id=%s error=%s", place_id, exc)
        return False
