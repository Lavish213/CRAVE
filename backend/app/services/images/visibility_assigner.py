from __future__ import annotations

import logging

from app.db.models.place_image import (
    VISIBILITY_HIDDEN,
    VISIBILITY_GALLERY_ONLY,
    VISIBILITY_CANDIDATE_PRIMARY,
    VISIBILITY_SHOWCASE,
)
from app.services.images.image_classifier import (
    CONTENT_FOOD_TYPES,
    CONTENT_MENU_TEXT,
    CONTENT_UNKNOWN,
)

logger = logging.getLogger(__name__)

# Thresholds
_THRESHOLD_HIDDEN = 0.20

# Food-typed images: must clear this to reach candidate_primary
_THRESHOLD_FOOD_CANDIDATE = 0.60

# Showcase requires both very high score AND identified food type
_THRESHOLD_SHOWCASE = 0.82

# Unknown-content images (e.g. opaque Google photo refs) get a slightly
# higher bar for candidate_primary so only position-0 best images qualify.
_THRESHOLD_UNKNOWN_CANDIDATE = 0.65


class VisibilityAssigner:
    """
    Phase 3 visibility assignment.

    Rules
    -----
    hidden:
        quality_score < 0.20

    gallery_only (default):
        0.20 <= score < candidate threshold
        OR content_type is menu_text (never primary)
        OR score meets threshold but content_type is non-food AND non-unknown

    candidate_primary:
        score >= 0.60 AND content_type in FOOD_TYPES
        OR score >= 0.65 AND content_type == unknown
        (position-0 Google photos land here via the 0.65 path)

    showcase:
        score >= 0.82 AND content_type in FOOD_TYPES

    Notes
    -----
    - menu_text images are always gallery_only regardless of score.
    - Interior / exterior images are gallery_only (not primary-eligible).
    - For datasets where all images are opaque Google refs (content=unknown),
      the position-based quality_score ensures only the top-ranked photo
      per place clears the 0.65 candidate_primary threshold.
    - Borderline images default to gallery_only, never hidden.
    """

    def assign(
        self,
        *,
        quality_score: float,
        content_type: str,
    ) -> str:
        score = float(quality_score)

        # Hidden: clearly bad
        if score < _THRESHOLD_HIDDEN:
            return VISIBILITY_HIDDEN

        # Menu text: never a primary candidate
        if content_type == CONTENT_MENU_TEXT:
            return VISIBILITY_GALLERY_ONLY

        is_food = content_type in CONTENT_FOOD_TYPES
        is_unknown = content_type == CONTENT_UNKNOWN

        # Showcase: excellent score + confirmed food image
        if score >= _THRESHOLD_SHOWCASE and is_food:
            return VISIBILITY_SHOWCASE

        # Candidate primary: good food image
        if score >= _THRESHOLD_FOOD_CANDIDATE and is_food:
            return VISIBILITY_CANDIDATE_PRIMARY

        # Candidate primary: high-position Google photo (unknown but best available)
        if score >= _THRESHOLD_UNKNOWN_CANDIDATE and is_unknown:
            return VISIBILITY_CANDIDATE_PRIMARY

        return VISIBILITY_GALLERY_ONLY
