from __future__ import annotations

from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from app.db.models.place_truth import PlaceTruth


TRUTH_TYPE_MENU = "menu"


def get_truth(
    *,
    db: Session,
    place_id: str,
    truth_type: str,
) -> Optional[PlaceTruth]:
    """
    Generic truth fetcher.

    Returns the PlaceTruth row or None.
    """

    return (
        db.query(PlaceTruth)
        .filter(
            PlaceTruth.place_id == place_id,
            PlaceTruth.truth_type == truth_type,
        )
        .one_or_none()
    )


def get_menu_truth(
    *,
    db: Session,
    place_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Fetch canonical menu JSON.

    Safe against corrupted DB rows and
    malformed JSON payloads.
    """

    truth = get_truth(
        db=db,
        place_id=place_id,
        truth_type=TRUTH_TYPE_MENU,
    )

    if not truth:
        return None

    payload = getattr(truth, "sources_json", None)

    if not payload:
        return None

    if not isinstance(payload, dict):
        return None

    # basic structural validation
    if "sections" not in payload:
        return None

    if "item_count" not in payload:
        payload["item_count"] = sum(
            len(section.get("items", []))
            for section in payload.get("sections", [])
        )

    return payload