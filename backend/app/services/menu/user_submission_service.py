from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.menu_submission import MenuSubmission
from app.db.models.place_claim import PlaceClaim
from app.services.menu.materialize_menu_truth import materialize_menu_truth
from app.services.menu.menu_publisher import MenuPublisher
from app.services.menu.normalization.fingerprint import build_menu_fingerprint

logger = logging.getLogger(__name__)

SOURCE_USER_SUBMISSION = "user_submission"
DEFAULT_SECTION = "Other"
DEFAULT_CURRENCY = "USD"

# Deliberately below a scraper's typical starting confidence (materialize's
# score_candidate_group multiplies this by is_verified_source's 1.15x and
# source_type's 1.0x default weight) — a moderator approved the *content*,
# but a single self-reported submission still shouldn't out-rank a
# corroborated multi-source scrape at the same base confidence.
SUBMISSION_CONFIDENCE = 0.75


def _coerce_price_cents(raw: object) -> Optional[int]:
    if raw is None or raw == "":
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def apply_approved_submission(*, db: Session, submission: MenuSubmission) -> int:
    """
    Writes every item on an approved MenuSubmission as a PlaceClaim
    (field="menu_item", source="user_submission"), then re-runs the exact
    same materialize_menu_truth -> MenuPublisher pipeline every scraped
    source already goes through — so the submission is scored and merged
    against whatever else exists for this place instead of silently
    overwriting it.

    Returns the number of MenuItem rows published for the place after
    materialization (0 if nothing cleared MIN_TRUTH_ITEMS, including the
    case where this submission alone isn't enough).
    """
    written = 0

    for raw_item in submission.items or []:
        if not isinstance(raw_item, dict):
            continue

        name = str(raw_item.get("name") or "").strip()
        if not name:
            continue

        section = str(raw_item.get("category") or "").strip() or DEFAULT_SECTION
        description = str(raw_item.get("description") or "").strip() or None
        price_cents = _coerce_price_cents(raw_item.get("price_cents"))

        fingerprint = build_menu_fingerprint(
            name=name, section=section, currency=DEFAULT_CURRENCY
        )

        payload = {
            "fingerprint": fingerprint,
            "name": name,
            "section": section,
            "price_cents": price_cents,
            "currency": DEFAULT_CURRENCY,
            "description": description,
            "source_type": "user_submitted",
        }

        existing = (
            db.query(PlaceClaim)
            .filter(
                PlaceClaim.place_id == submission.place_id,
                PlaceClaim.field == "menu_item",
                PlaceClaim.claim_key == fingerprint,
                PlaceClaim.source == SOURCE_USER_SUBMISSION,
            )
            .one_or_none()
        )

        if existing:
            existing.value_json = payload
            existing.confidence = SUBMISSION_CONFIDENCE
            existing.is_verified_source = True
            existing.is_user_submitted = True
        else:
            db.add(
                PlaceClaim(
                    place_id=submission.place_id,
                    field="menu_item",
                    claim_key=fingerprint,
                    value_json=payload,
                    confidence=SUBMISSION_CONFIDENCE,
                    weight=1.0,
                    source=SOURCE_USER_SUBMISSION,
                    is_verified_source=True,
                    is_user_submitted=True,
                )
            )
        written += 1

    if written == 0:
        return 0

    db.commit()

    menu = materialize_menu_truth(db=db, place_id=submission.place_id)
    if menu is None:
        return 0

    try:
        published_count = MenuPublisher().publish(place_id=submission.place_id, db=db)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "menu_submission_publish_failed submission_id=%s place_id=%s",
            submission.id, submission.place_id,
        )
        return 0

    return published_count
