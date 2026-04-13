from __future__ import annotations

import logging
from typing import Dict, List


logger = logging.getLogger(__name__)


SOURCE_WEIGHTS = {
    "google": 0.85,
    "provider": 0.9,
    "website": 1.0,
    "unknown": 0.6,
}

MIN_ACCEPTABLE_SCORE = 0.2


class ImageScorer:
    """
    Assign a confidence score to image candidates.

    Factors
    -------
    source reliability
    image resolution
    context hints
    """

    def score(
        self,
        *,
        place,
        candidates: List[dict],
    ) -> List[dict]:

        if not candidates:
            return []

        place_id = getattr(place, "id", None)

        scored: List[dict] = []

        for candidate in candidates:

            try:

                score = self._score_candidate(candidate)

                if score < MIN_ACCEPTABLE_SCORE:
                    continue

                candidate["score"] = score

                scored.append(candidate)

            except Exception as exc:

                logger.debug(
                    "image_score_failed place_id=%s error=%s",
                    place_id,
                    exc,
                )

        logger.info(
            "image_scoring_complete place_id=%s input=%s scored=%s",
            place_id,
            len(candidates),
            len(scored),
        )

        return scored

    # ---------------------------------------------------------
    # Candidate scoring
    # ---------------------------------------------------------

    def _score_candidate(
        self,
        candidate: Dict,
    ) -> float:

        source = candidate.get("source", "unknown")

        base_score = SOURCE_WEIGHTS.get(source, SOURCE_WEIGHTS["unknown"])

        resolution_score = self._resolution_score(candidate)

        context_score = self._context_score(candidate)

        score = base_score * resolution_score * context_score

        if score > 1.0:
            score = 1.0

        if score < 0.0:
            score = 0.0

        return score

    def _resolution_score(
        self,
        candidate: Dict,
    ) -> float:

        width = candidate.get("width")
        height = candidate.get("height")

        if not width or not height:
            return 0.8

        try:

            width = int(width)
            height = int(height)

            pixels = width * height

            if pixels >= 2_000_000:
                return 1.2

            if pixels >= 1_000_000:
                return 1.1

            if pixels >= 300_000:
                return 1.0

            return 0.7

        except Exception:

            return 0.8

    def _context_score(
        self,
        candidate: Dict,
    ) -> float:

        context = candidate.get("context")

        if not context:
            return 1.0

        context = str(context).lower()

        if "hero" in context:
            return 1.2

        if "gallery" in context:
            return 1.1

        if "menu" in context:
            return 0.9

        return 1.0