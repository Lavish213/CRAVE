from __future__ import annotations

import logging
from typing import List


logger = logging.getLogger(__name__)


MAX_RANKED_IMAGES = 30


class ImageRanker:
    """
    Orders image candidates based on score and quality signals.

    Responsibilities
    ----------------
    - deterministic ordering
    - prefer high score
    - prefer higher resolution
    - keep ranking stable
    """

    def rank(
        self,
        *,
        place,
        candidates: List[dict],
    ) -> List[dict]:

        if not candidates:
            return []

        place_id = getattr(place, "id", None)

        try:

            ranked = sorted(
                candidates,
                key=lambda c: (
                    self._score(c),
                    self._resolution(c),
                    self._source_priority(c),
                ),
                reverse=True,
            )

            ranked = ranked[:MAX_RANKED_IMAGES]

            logger.info(
                "image_rank_complete place_id=%s input=%s output=%s",
                place_id,
                len(candidates),
                len(ranked),
            )

            return ranked

        except Exception as exc:

            logger.debug(
                "image_rank_failed place_id=%s error=%s",
                place_id,
                exc,
            )

            return []

    # ---------------------------------------------------------
    # Ranking helpers
    # ---------------------------------------------------------

    def _score(
        self,
        candidate: dict,
    ) -> float:

        try:
            return float(candidate.get("score", 0.0))
        except Exception:
            return 0.0

    def _resolution(
        self,
        candidate: dict,
    ) -> int:

        width = candidate.get("width")
        height = candidate.get("height")

        try:

            if width and height:
                return int(width) * int(height)

        except Exception:
            pass

        return 0

    def _source_priority(
        self,
        candidate: dict,
    ) -> int:

        source = candidate.get("source")

        priority_map = {
            "website": 3,
            "provider": 2,
            "google": 1,
            "unknown": 0,
        }

        return priority_map.get(source, 0)