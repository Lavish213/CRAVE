from __future__ import annotations

import logging
from typing import List

from app.db.models.place import Place


logger = logging.getLogger(__name__)


CONFIDENCE_THRESHOLD = 0.5
VALIDATION_THRESHOLD = 0.5


def _needs_review(place: Place) -> bool:
    """
    Determine if a place should generate discovery candidates.
    """

    confidence = getattr(place, "confidence_score", None)
    validation = getattr(place, "local_validation", None)

    if confidence is not None and confidence < CONFIDENCE_THRESHOLD:
        return True

    if validation is not None and validation < VALIDATION_THRESHOLD:
        return True

    return False


def select_candidates(
    *,
    places: List[Place],
    limit: int = 50,
) -> List[Place]:
    """
    Select places that require discovery candidate processing.

    Logic:
    - low confidence
    - low local validation
    - prioritizes lowest scores first
    """

    candidates: List[Place] = []

    for place in places:

        try:

            if _needs_review(place):
                candidates.append(place)

        except Exception as exc:

            logger.debug(
                "candidate_selector_skip place_id=%s error=%s",
                getattr(place, "id", None),
                exc,
            )

    # prioritize lowest confidence first
    candidates.sort(
        key=lambda p: (
            getattr(p, "confidence_score", 1.0),
            getattr(p, "local_validation", 1.0),
        )
    )

    selected = candidates[:limit]

    logger.info(
        "candidate_selector_complete selected=%s scanned=%s",
        len(selected),
        len(places),
    )

    return selected