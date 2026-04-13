from __future__ import annotations

import logging
from typing import Dict, List
from urllib.parse import urlparse


logger = logging.getLogger(__name__)


MIN_URL_LENGTH = 15
MIN_DIMENSION = 80

BLOCKED_PATH_KEYWORDS = {
    "logo",
    "icon",
    "avatar",
    "profile",
    "sprite",
    "placeholder",
    "default",
    "favicon",
}

BLOCKED_EXTENSIONS = {
    ".svg",
}


class ImageMatcher:
    """
    Validate and normalize image candidates before dedupe and scoring.

    Responsibilities
    ----------------
    - reject obvious non-restaurant images
    - reject icons / logos
    - reject tiny assets
    - ensure candidate structure integrity
    - attach normalization metadata
    """

    def match(
        self,
        *,
        place,
        candidates: List[dict],
    ) -> List[dict]:

        if not candidates:
            return []

        place_id = getattr(place, "id", None)

        matched: List[dict] = []

        for candidate in candidates:

            try:

                if not self._is_valid_candidate(candidate):
                    continue

                if not self._is_valid_url(candidate["url"]):
                    continue

                if self._is_blocked_asset(candidate["url"]):
                    continue

                if not self._dimension_valid(candidate):
                    continue

                normalized = self._normalize_candidate(
                    place_id=place_id,
                    candidate=candidate,
                )

                if normalized:
                    matched.append(normalized)

            except Exception as exc:

                logger.debug(
                    "image_matcher_candidate_failed error=%s",
                    exc,
                )

        logger.info(
            "image_matcher_complete place_id=%s input=%s matched=%s",
            place_id,
            len(candidates),
            len(matched),
        )

        return matched

    # ---------------------------------------------------------
    # Candidate validation
    # ---------------------------------------------------------

    def _is_valid_candidate(
        self,
        candidate: Dict,
    ) -> bool:

        if not isinstance(candidate, dict):
            return False

        url = candidate.get("url")

        if not url:
            return False

        if len(str(url)) < MIN_URL_LENGTH:
            return False

        return True

    def _dimension_valid(
        self,
        candidate: Dict,
    ) -> bool:

        width = candidate.get("width")
        height = candidate.get("height")

        if width is None or height is None:
            return True

        try:

            width = int(width)
            height = int(height)

            if width < MIN_DIMENSION or height < MIN_DIMENSION:
                return False

            return True

        except Exception:
            return True

    # ---------------------------------------------------------
    # URL validation
    # ---------------------------------------------------------

    def _is_valid_url(
        self,
        url: str,
    ) -> bool:

        try:

            parsed = urlparse(url)

            if parsed.scheme not in {"http", "https"}:
                return False

            if not parsed.netloc:
                return False

            return True

        except Exception:
            return False

    def _is_blocked_asset(
        self,
        url: str,
    ) -> bool:

        try:

            path = urlparse(url).path.lower()

            if any(keyword in path for keyword in BLOCKED_PATH_KEYWORDS):
                return True

            if any(path.endswith(ext) for ext in BLOCKED_EXTENSIONS):
                return True

            return False

        except Exception:
            return False

    # ---------------------------------------------------------
    # Normalization
    # ---------------------------------------------------------

    def _normalize_candidate(
        self,
        *,
        place_id: str,
        candidate: Dict,
    ) -> Dict | None:

        try:

            url = str(candidate["url"]).strip()

            normalized: Dict = {
                "place_id": place_id,
                "url": url,
                "source": candidate.get("source", "unknown"),
                "width": candidate.get("width"),
                "height": candidate.get("height"),
                "context": candidate.get("context"),
                "metadata": candidate.get("metadata", {}),
            }

            return normalized

        except Exception:
            return None