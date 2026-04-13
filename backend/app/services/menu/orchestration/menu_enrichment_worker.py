from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.enrichment_job import EnrichmentJob
from app.db.models.menu_source import MenuSource
from app.db.models.place import Place
from app.services.menu.claims.menu_claim_builder import build_menu_items
from app.services.menu.extraction.extract_menu_from_url import extract_menu_from_url
from app.services.menu.orchestration.ingest_menu_items import ingest_menu_items


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_menu_items(menu_result: Any) -> list[Any]:
    if menu_result is None:
        return []

    if isinstance(menu_result, list):
        return menu_result

    extracted_items = getattr(menu_result, "items", None)
    if isinstance(extracted_items, list):
        return extracted_items

    if isinstance(menu_result, dict):
        dict_items = menu_result.get("items")
        if isinstance(dict_items, list):
            return dict_items

    return []


def _resolve_menu_url(db: Session, place: Place) -> str | None:
    website = (getattr(place, "website", None) or "").strip()
    if website:
        return website

    menu_source = (
        db.query(MenuSource)
        .filter(
            MenuSource.place_id == place.id,
            MenuSource.is_active.is_(True),
        )
        .order_by(MenuSource.last_seen_at.desc(), MenuSource.created_at.desc())
        .first()
    )

    if not menu_source:
        return None

    source_url = (getattr(menu_source, "source_url", None) or "").strip()
    if source_url:
        return source_url

    return None


def _mark_job_failed(
    db: Session,
    job: EnrichmentJob,
    error: str,
) -> None:
    now = _utcnow()
    job.status = "failed"
    job.last_error = error
    job.is_active = False
    job.locked_at = None
    job.completed_at = now
    job.updated_at = now
    db.commit()


def process_menu_job(
    db: Session,
    job: EnrichmentJob,
) -> None:
    """
    Process a single menu enrichment job.

    Flow:
    - mark running
    - load place
    - resolve usable menu URL
    - extract menu
    - normalize extracted items
    - build claims
    - ingest into DB
    - update place flags
    - mark job complete
    """

    try:
        now = _utcnow()

        job.status = "running"
        job.locked_at = now
        job.attempts = (job.attempts or 0) + 1
        job.last_attempted_at = now
        job.updated_at = now
        db.commit()

        place = db.query(Place).filter(Place.id == job.place_id).first()
        if not place:
            _mark_job_failed(db, job, "missing_place")
            return

        url = _resolve_menu_url(db, place)
        if not url:
            _mark_job_failed(db, job, "missing_menu_url")
            return

        extracted = extract_menu_from_url(
            db=db,
            place_id=place.id,
            url=url,
        )

        menu_items = _normalize_menu_items(extracted)

        claims = build_menu_items(
            place_id=place.id,
            items=menu_items,
        ) or []

        ingest_menu_items(
            db=db,
            place_id=place.id,
            claims=claims,
        )

        finished_at = _utcnow()

        if claims:
            place.has_menu = True
            place.last_menu_updated_at = finished_at

        job.status = "done"
        job.completed_at = finished_at
        job.last_error = None
        job.is_active = False
        job.locked_at = None
        job.updated_at = finished_at

        db.commit()

    except Exception as e:
        _mark_job_failed(db, job, str(e))
