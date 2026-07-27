from __future__ import annotations

import logging
import re
from typing import Tuple

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Content type constants
# ------------------------------------------------------------------

CONTENT_PLATED_FOOD = "plated_food"
CONTENT_FOOD_CLOSEUP = "food_closeup"
CONTENT_RESTAURANT_INTERIOR = "restaurant_interior"
CONTENT_MENU_TEXT = "menu_text"
CONTENT_EXTERIOR = "exterior"
CONTENT_UNKNOWN = "unknown"

# Types eligible for primary selection
CONTENT_FOOD_TYPES = frozenset({CONTENT_PLATED_FOOD, CONTENT_FOOD_CLOSEUP})

# ------------------------------------------------------------------
# URL pattern matchers
# ------------------------------------------------------------------

_MENU_RE = re.compile(
    r"menu|item[-_]photo|food[-_]item|dish[-_]image",
    re.IGNORECASE,
)
_FOOD_CLOSEUP_RE = re.compile(
    r"closeup|close[-_]up|macro|detail",
    re.IGNORECASE,
)
_FOOD_RE = re.compile(
    r"/food/|/dish/|/plate/|/meal/|plated|entree|appetizer|dessert|cuisine",
    re.IGNORECASE,
)
_INTERIOR_RE = re.compile(
    r"interior|inside|dining[-_]room|seating|ambiance|decor|atmosphere",
    re.IGNORECASE,
)
_EXTERIOR_RE = re.compile(
    r"exterior|outside|storefront|facade|frontage",
    re.IGNORECASE,
)
_THUMBNAIL_RE = re.compile(
    r"thumb|thumbnail|/small/|/tiny/|/icon/|logo|avatar|sprite|\.svg",
    re.IGNORECASE,
)
_HERO_RE = re.compile(
    r"hero|banner|/large/|/full/|hires|high[-_]res|original|[_\-]1200|[_\-]1600|[_\-]2000",
    re.IGNORECASE,
)

# Opaque Google Places photo URL prefix — no content hints in these
_GOOGLE_PLACES_PHOTO_RE = re.compile(
    r"places\.googleapis\.com/v1/places/[^/]+/photos/",
    re.IGNORECASE,
)

# Content quality multipliers
_CONTENT_MULTIPLIERS = {
    CONTENT_PLATED_FOOD: 1.10,
    CONTENT_FOOD_CLOSEUP: 1.05,
    CONTENT_RESTAURANT_INTERIOR: 0.95,
    CONTENT_EXTERIOR: 0.90,
    CONTENT_MENU_TEXT: 0.65,
    CONTENT_UNKNOWN: 0.90,
}

# Position scores: Google returns photos in quality-ranked order.
# Position 0 is their best / most-relevant photo (typically food).
# Beyond index 7 → floor at 0.40.
_POSITION_SCORES = [1.00, 0.78, 0.65, 0.56, 0.50, 0.46, 0.43, 0.41]
_POSITION_FLOOR = 0.40


class ImageClassifier:
    """
    Phase 3 heuristic classifier. No pixel fetching — pure heuristics.

    For provider/website images: URL keyword patterns determine content_type.
    For opaque Google Places photo URLs: content_type = unknown, but
    ``position_in_place`` (Google's own quality ranking) drives quality_score.

    Parameters
    ----------
    url : str
        Stored image URL.
    confidence : float
        Existing ingestion confidence score (source × resolution × context).
    position_in_place : int
        Zero-based index of this image within its place's image set,
        ordered by insertion date ascending (= Google's quality rank).
        Default 0 if unknown.

    Returns
    -------
    (content_type, quality_score)
    quality_score is normalized to [0.0, 1.0].
    """

    def classify(
        self,
        *,
        url: str,
        confidence: float,
        position_in_place: int = 0,
    ) -> Tuple[str, float]:
        content_type = self._classify_content(url)
        quality_score = self._compute_quality(
            url=url,
            confidence=confidence,
            content_type=content_type,
            position_in_place=position_in_place,
        )
        return content_type, quality_score

    # ------------------------------------------------------------------
    # Content type classification
    # ------------------------------------------------------------------

    def _classify_content(self, url: str) -> str:
        # Google Places photo refs are opaque — no URL hints, skip keyword checks
        if _GOOGLE_PLACES_PHOTO_RE.search(url):
            return CONTENT_UNKNOWN

        # Provider / website URLs: check keyword patterns
        if _MENU_RE.search(url):
            return CONTENT_MENU_TEXT

        if _FOOD_CLOSEUP_RE.search(url):
            return CONTENT_FOOD_CLOSEUP

        if _FOOD_RE.search(url):
            return CONTENT_PLATED_FOOD

        if _INTERIOR_RE.search(url):
            return CONTENT_RESTAURANT_INTERIOR

        if _EXTERIOR_RE.search(url):
            return CONTENT_EXTERIOR

        return CONTENT_UNKNOWN

    # ------------------------------------------------------------------
    # Quality score
    # ------------------------------------------------------------------

    def _compute_quality(
        self,
        *,
        url: str,
        confidence: float,
        content_type: str,
        position_in_place: int,
    ) -> float:
        base = max(0.0, min(1.0, float(confidence)))
        content_mult = _CONTENT_MULTIPLIERS.get(content_type, 0.90)
        url_mult = self._url_quality_mult(url)
        position_mult = self._position_mult(position_in_place)

        raw = base * content_mult * url_mult * position_mult

        return round(max(0.0, min(1.0, raw)), 4)

    def _position_mult(self, position: int) -> float:
        """
        Converts Google's photo ordering into a quality multiplier.
        Position 0 = best photo (mult=1.0), decays with each subsequent image.
        """
        if position < 0:
            position = 0
        if position < len(_POSITION_SCORES):
            return _POSITION_SCORES[position]
        return _POSITION_FLOOR

    def _url_quality_mult(self, url: str) -> float:
        if _THUMBNAIL_RE.search(url):
            return 0.65
        if _HERO_RE.search(url):
            return 1.10
        return 1.0
