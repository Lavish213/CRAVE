"""
MenuImageBridge — Phase 3-compliant ingest for menu item images.

Connects the menu extraction pipeline to the Phase 3 image pipeline.
Every image from a menu provider (Toast item imageUrl, etc.) must pass
through classify → score → visibility assign → write → re-elect primary.

No bypass. Phase 3 is law.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.place_image import (
    PlaceImage,
    VISIBILITY_GALLERY_ONLY,
    VISIBILITY_HIDDEN,
)
from app.services.images.image_classifier import ImageClassifier
from app.services.images.visibility_assigner import VisibilityAssigner
from app.services.images.place_image_invariant_service import PlaceImageInvariantService


logger = logging.getLogger(__name__)

# Provider menu images have high source confidence — they come from the
# restaurant's own ordering system (e.g. Toast item photos).
_PROVIDER_CONFIDENCE = 0.85

# Never write more than this many item images per place in one pass.
_MAX_ITEM_IMAGES_PER_PLACE = 20


class MenuImageBridge:
    """
    Ingests item-level images from menu extraction into place_images,
    running each through the full Phase 3 classification pipeline.

    Usage
    -----
    bridge = MenuImageBridge()
    result = bridge.ingest(db=db, place_id=place_id, image_urls=urls)
    """

    def __init__(self) -> None:
        self._classifier = ImageClassifier()
        self._assigner = VisibilityAssigner()
        self._invariant = PlaceImageInvariantService()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest(
        self,
        *,
        db: Session,
        place_id: str,
        image_urls: List[str],
        source: str = "menu_item",
        base_confidence: float = _PROVIDER_CONFIDENCE,
    ) -> dict:
        """
        Classify and persist menu item images for a place.

        Parameters
        ----------
        db : Session
        place_id : str
        image_urls : list of URL strings (may include None, will be skipped)
        source : label for logging (e.g. "toast_item", "popmenu_item")
        base_confidence : ingestion-layer confidence (default 0.85 for provider)

        Returns
        -------
        dict with keys: inserted, updated, skipped, hidden_count
        """
        if not place_id:
            raise ValueError("place_id required")

        clean_urls = self._clean_urls(image_urls)

        if not clean_urls:
            return {"inserted": 0, "updated": 0, "skipped": 0, "hidden_count": 0}

        cap = min(len(clean_urls), _MAX_ITEM_IMAGES_PER_PLACE)
        clean_urls = clean_urls[:cap]

        existing = self._load_existing(db, place_id)
        existing_by_url = {img.url: img for img in existing}

        inserted = 0
        updated = 0
        skipped = 0
        hidden_count = 0

        for position, url in enumerate(clean_urls):

            content_type, quality_score = self._classifier.classify(
                url=url,
                confidence=base_confidence,
                position_in_place=position,
            )

            visibility = self._assigner.assign(
                quality_score=quality_score,
                content_type=content_type,
            )

            if visibility == VISIBILITY_HIDDEN:
                hidden_count += 1
                logger.debug(
                    "menu_image_bridge.hidden place_id=%s url=%.80s score=%s",
                    place_id,
                    url,
                    quality_score,
                )
                skipped += 1
                continue

            existing_image = existing_by_url.get(url)

            if existing_image:
                # Update scores if new run produced better signal
                changed = False

                if quality_score > (existing_image.quality_score or 0.0):
                    existing_image.quality_score = quality_score
                    changed = True

                if content_type and not existing_image.content_type:
                    existing_image.content_type = content_type
                    changed = True

                if visibility != existing_image.visibility_status:
                    existing_image.visibility_status = visibility
                    changed = True

                if changed:
                    updated += 1
            else:
                new_image = PlaceImage(
                    place_id=place_id,
                    url=url,
                    is_primary=False,
                    confidence=base_confidence,
                    quality_score=quality_score,
                    content_type=content_type,
                    visibility_status=visibility,
                )
                db.add(new_image)
                existing_by_url[url] = new_image
                inserted += 1

        if inserted or updated:
            db.flush()
            # Re-election: enforce invariants and promote best primary
            self._invariant.repair(db=db, place_id=place_id)
            db.flush()

        summary = {
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "hidden_count": hidden_count,
        }

        logger.info(
            "menu_image_bridge.complete place_id=%s source=%s %s",
            place_id,
            source,
            summary,
        )

        return summary

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _clean_urls(self, urls: List[Optional[str]]) -> List[str]:
        out: List[str] = []
        seen: set = set()

        for raw in urls or []:
            if not raw or not isinstance(raw, str):
                continue

            url = raw.strip()

            if not url or not url.startswith("http"):
                continue

            if url in seen:
                continue

            seen.add(url)
            out.append(url)

        return out

    def _load_existing(
        self,
        db: Session,
        place_id: str,
    ) -> List[PlaceImage]:
        stmt = select(PlaceImage).where(PlaceImage.place_id == place_id)
        return list(db.execute(stmt).scalars().all())
