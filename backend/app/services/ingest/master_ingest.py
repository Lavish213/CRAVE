from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.services.matching.place_matcher import match_place
from app.services.menu.processing.menu_orchestrator import MenuOrchestrator
from app.services.menu.extraction.extract_menu_from_url import extract_menu_from_url
from app.services.menu.extraction.fetch_html import fetch_html
from app.services.menu.fetchers.grubhub_fetcher import fetch_grubhub_menu


logger = logging.getLogger(__name__)


MAX_PLACES_PER_RUN = 50


def run_master_ingest(db: Session) -> None:

    places: List[Place] = (
        db.query(Place)
        .filter(Place.is_active == True)
        .limit(MAX_PLACES_PER_RUN)
        .all()
    )

    logger.info("master_ingest_start count=%s", len(places))

    for place in places:
        try:
            _process_place(db, place)
        except Exception as exc:
            db.rollback()
            logger.exception(
                "master_ingest_place_failed place_id=%s error=%s",
                getattr(place, "id", None),
                exc,
            )

    logger.info("master_ingest_complete")


def _process_place(db: Session, place: Place) -> None:

    place_id = getattr(place, "id", None)

    logger.info("process_place_start place_id=%s", place_id)

    # -----------------------------------------------------
    # STEP 1 — MATCH PROVIDER
    # -----------------------------------------------------

    try:
        provider_candidates = _get_provider_candidates(place)

        match = match_place(
            local_place=place,
            provider_places=provider_candidates,
        )

        if match and getattr(match, "matched", False):
            _attach_provider(place, match)

    except Exception as exc:
        logger.warning("provider_match_failed place_id=%s error=%s", place_id, exc)

    # -----------------------------------------------------
    # STEP 2 — FETCH (GRUBHUB FIRST)
    # -----------------------------------------------------

    grubhub_payload: Optional[dict] = None

    try:
        grubhub_payload = fetch_grubhub_menu(
            place,
            fetcher=_http_fetch_wrapper,
        )
    except Exception as exc:
        logger.warning("grubhub_fetch_failed place_id=%s error=%s", place_id, exc)

    if grubhub_payload:
        place.grubhub_payload = grubhub_payload
        logger.info("grubhub_payload_attached place_id=%s", place_id)

    # -----------------------------------------------------
    # STEP 3 — EXTRACTION PIPELINE
    # -----------------------------------------------------

    url = getattr(place, "menu_source_url", None) or getattr(place, "website", None)

    if url:
        try:
            extract_menu_from_url(
                db=db,
                place_id=place_id,
                url=url,
            )
        except Exception as exc:
            logger.warning(
                "menu_extraction_failed place_id=%s url=%s error=%s",
                place_id,
                url,
                exc,
            )

    # -----------------------------------------------------
    # STEP 4 — ORCHESTRATOR (CLAIMS + TRUTH)
    # -----------------------------------------------------

    try:
        result = MenuOrchestrator().run_for_place(
            db=db,
            place=place,
        )

        logger.info(
            "orchestrator_complete place_id=%s extracted=%s claims=%s",
            place_id,
            getattr(result, "extracted_item_count", 0),
            getattr(result, "emitted_claim_count", 0),
        )

    except Exception as exc:
        logger.exception(
            "orchestrator_failed place_id=%s error=%s",
            place_id,
            exc,
        )

    # -----------------------------------------------------
    # SAFE COMMIT
    # -----------------------------------------------------

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("db_commit_failed place_id=%s error=%s", place_id, exc)


def _get_provider_candidates(place: Place) -> List[dict]:
    return []


def _attach_provider(place: Place, match) -> None:

    try:
        place.menu_source_url = match.provider_url
        place.external_id = match.provider_id

        logger.info(
            "provider_attached place_id=%s provider_id=%s",
            getattr(place, "id", None),
            match.provider_id,
        )

    except Exception as exc:
        logger.warning(
            "provider_attach_failed place_id=%s error=%s",
            getattr(place, "id", None),
            exc,
        )


def _http_fetch_wrapper(url: str):
    try:
        return fetch_html(url)
    except Exception:
        return None