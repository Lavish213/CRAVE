from __future__ import annotations

import logging
from typing import List, Dict


logger = logging.getLogger(__name__)


DEFAULT_GALLERY_LIMIT = 8
MIN_PRIMARY_SCORE = 0.25


class ImageSelector:
    """
    Chooses the final set of images for a place.

    Responsibilities
    ----------------
    - pick a primary image
    - limit gallery size
    - enforce quality threshold
    - keep deterministic ordering
    """

    def select(
        self,
        *,
        place,
        candidates: List[dict],
        max_gallery_images: int = DEFAULT_GALLERY_LIMIT,
    ) -> List[dict]:

        if not candidates:
            return []

        place_id = getattr(place, "id", None)

        try:

            selected: List[Dict] = []

            primary = self._select_primary(candidates)

            if primary:
                primary["is_primary"] = True
                selected.append(primary)

            for candidate in candidates:

                if candidate is primary:
                    continue

                if len(selected) >= max_gallery_images:
                    break

                if not self._eligible(candidate):
                    continue

                candidate["is_primary"] = False

                selected.append(candidate)

            logger.info(
                "image_selection_complete place_id=%s input=%s selected=%s",
                place_id,
                len(candidates),
                len(selected),
            )

            return selected

        except Exception as exc:

            logger.debug(
                "image_selection_failed place_id=%s error=%s",
                place_id,
                exc,
            )

            return []

    # ---------------------------------------------------------
    # Primary selection
    # ---------------------------------------------------------

    def _select_primary(
        self,
        candidates: List[dict],
    ) -> Dict | None:

        for candidate in candidates:

            score = self._score(candidate)

            if score >= MIN_PRIMARY_SCORE:
                return candidate

        return candidates[0] if candidates else None

    # ---------------------------------------------------------
    # Eligibility checks
    # ---------------------------------------------------------

    def _eligible(
        self,
        candidate: Dict,
    ) -> bool:

        score = self._score(candidate)

        if score <= 0:
            return False

        return True

    def _score(
        self,
        candidate: Dict,
    ) -> float:

        try:
            return float(candidate.get("score", 0.0))
        except Exception:
            return 0.0