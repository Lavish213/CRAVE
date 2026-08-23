"""
PlaceImageInvariantService — enforces all hard invariants on place images.

Hard invariants (must always hold):
  - Only ONE primary per place
  - Hidden image cannot be primary
  - Primary must exist OR be null (never stale)
  - No orphan images (handled at DB level via CASCADE)
  - No duplicate primary

Call after every mutation that touches is_primary or visibility_status.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models.place_image import (
    PlaceImage,
    VISIBILITY_HIDDEN,
    VISIBILITY_GALLERY_ONLY,
)

logger = logging.getLogger(__name__)


def _is_ephemeral_google_ref(url: Optional[str]) -> bool:
    """
    True for a raw Google Places (New) photo reference — either the bare
    resource name ("places/{id}/photos/{id}") or the full
    places.googleapis.com URL. These are session-scoped: the same string
    can go dead (404/400 upstream) at any time, unlike a durable R2/CDN
    URL. Used to keep winner-selection below from picking a high-
    confidence-but-possibly-dead Google reference over a working durable
    photo just because it scored higher at ingestion time — confidence
    reflects extraction quality, not whether the URL still resolves.
    """
    if not url:
        return False
    return url.startswith("places/") or "places.googleapis.com" in url


class PlaceImageInvariantService:
    """
    Enforces and repairs hard invariants on place_images.

    Usage
    -----
    Call repair() after any mutation to place_images that affects
    is_primary or visibility_status.
    """

    def repair(
        self,
        *,
        db: Session,
        place_id: str,
    ) -> dict:
        """
        Runs all invariant checks and repairs for a place.

        Returns a summary of what was found and fixed.
        """
        if not place_id:
            raise ValueError("place_id required")

        result = {
            "place_id": place_id,
            "hidden_primary_fixed": False,
            "duplicate_primary_fixed": False,
            "orphan_primary_fixed": False,
        }

        try:
            images = self._load_images(db, place_id)

            if not images:
                return result

            result["hidden_primary_fixed"] = self._fix_hidden_primary(db, images)
            result["duplicate_primary_fixed"] = self._fix_duplicate_primary(db, images)

            db.flush()

            logger.info(
                "invariant_repair_complete place_id=%s %s",
                place_id,
                result,
            )

        except Exception as exc:
            logger.exception(
                "invariant_repair_failed place_id=%s error=%s",
                place_id,
                exc,
            )

        return result

    def check(
        self,
        *,
        db: Session,
        place_id: str,
    ) -> dict:
        """
        Read-only check. Returns violations without fixing.
        Use for auditing.
        """
        if not place_id:
            raise ValueError("place_id required")

        violations = {
            "place_id": place_id,
            "hidden_primary": False,
            "duplicate_primary": False,
            "primary_count": 0,
        }

        images = self._load_images(db, place_id)
        primaries = [img for img in images if img.is_primary]

        violations["primary_count"] = len(primaries)
        violations["hidden_primary"] = any(
            img.visibility_status == VISIBILITY_HIDDEN for img in primaries
        )
        violations["duplicate_primary"] = len(primaries) > 1

        if any(violations[k] for k in ("hidden_primary", "duplicate_primary")):
            logger.warning(
                "invariant_violation_detected place_id=%s violations=%s",
                place_id,
                violations,
            )

        return violations

    # ---------------------------------------------------------
    # Internal repairs
    # ---------------------------------------------------------

    def _fix_hidden_primary(
        self,
        db: Session,
        images: List[PlaceImage],
    ) -> bool:
        """
        Hidden image cannot be primary.
        Demotes any hidden primary; promotes best eligible replacement.
        """
        hidden_primaries = [
            img for img in images
            if img.is_primary and img.visibility_status == VISIBILITY_HIDDEN
        ]

        if not hidden_primaries:
            return False

        for img in hidden_primaries:
            img.is_primary = False
            logger.warning(
                "invariant_hidden_primary_demoted image_id=%s place_id=%s",
                img.id,
                img.place_id,
            )

        # Promote best eligible replacement
        self._promote_best_eligible(images)

        return True

    def _fix_duplicate_primary(
        self,
        db: Session,
        images: List[PlaceImage],
    ) -> bool:
        """
        Only one primary allowed per place.
        Keeps the highest-confidence non-hidden primary, demotes the rest.
        """
        primaries = [img for img in images if img.is_primary]

        if len(primaries) <= 1:
            return False

        # Pick best: prefer non-hidden, prefer a durable (non-ephemeral)
        # URL over a raw Google reference regardless of confidence — see
        # _is_ephemeral_google_ref's docstring — then highest confidence
        # within that.
        eligible = [
            img for img in primaries
            if img.visibility_status != VISIBILITY_HIDDEN
        ]

        winner = max(
            eligible or primaries,
            key=lambda img: (
                not _is_ephemeral_google_ref(img.url),
                img.quality_score if img.quality_score is not None else img.confidence or 0.0,
            ),
        )

        for img in primaries:
            if img is not winner:
                img.is_primary = False
                logger.warning(
                    "invariant_duplicate_primary_demoted image_id=%s place_id=%s",
                    img.id,
                    img.place_id,
                )

        return True

    def _promote_best_eligible(
        self,
        images: List[PlaceImage],
    ) -> Optional[PlaceImage]:
        """
        Promotes best eligible image to primary after a demotion.
        Eligible = not hidden, has highest confidence.
        No-op if a valid non-hidden primary already exists.
        """
        # Guard: don't promote if a valid primary already exists
        valid_existing = [
            img for img in images
            if img.is_primary and img.visibility_status != VISIBILITY_HIDDEN
        ]
        if valid_existing:
            return None

        candidates = [
            img for img in images
            if not img.is_primary and img.visibility_status != VISIBILITY_HIDDEN
        ]

        if not candidates:
            return None

        # Prefer a durable (non-ephemeral) URL over a raw Google reference
        # regardless of confidence — see _is_ephemeral_google_ref's
        # docstring — then quality_score (Phase 3 signal) over ingestion
        # confidence.
        best = max(
            candidates,
            key=lambda img: (
                not _is_ephemeral_google_ref(img.url),
                img.quality_score if img.quality_score is not None else img.confidence or 0.0,
            ),
        )
        best.is_primary = True

        logger.info(
            "invariant_primary_promoted image_id=%s place_id=%s confidence=%s",
            best.id,
            best.place_id,
            best.confidence,
        )

        return best

    def _load_images(
        self,
        db: Session,
        place_id: str,
    ) -> List[PlaceImage]:
        stmt = select(PlaceImage).where(PlaceImage.place_id == place_id)
        return list(db.execute(stmt).scalars().all())
