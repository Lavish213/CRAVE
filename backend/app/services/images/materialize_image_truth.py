from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.db.models.place_image import PlaceImage


logger = logging.getLogger(__name__)

UTC = timezone.utc


def _utcnow() -> datetime:
    return datetime.now(UTC)


class MaterializeImageTruth:
    """
    Persist final gallery images to the database.

    Responsibilities
    ----------------
    - write images to place_images
    - enforce unique (place_id, url)
    - update primary image
    - remain idempotent
    """

    def write(
        self,
        *,
        db: Session,
        place: Place,
        gallery_payload: Dict,
        force_refresh: bool = False,
    ) -> List[PlaceImage]:

        place_id = getattr(place, "id", None)

        if not place_id:
            raise ValueError("place.id required")

        gallery = gallery_payload.get("gallery") or []
        primary = gallery_payload.get("primary")

        if not gallery:
            return []

        try:

            existing = self._existing_images(db=db, place_id=place_id)

            existing_by_url = {img.url: img for img in existing}

            written: List[PlaceImage] = []

            primary_url = primary.get("url") if primary else None

            for entry in gallery:

                try:

                    url = entry.get("url")

                    if not url:
                        continue

                    score = entry.get("score", 0.5)

                    image = existing_by_url.get(url)

                    if image:

                        if url == primary_url:
                            image.is_primary = True

                        image.confidence = max(image.confidence, score)

                        written.append(image)

                        continue

                    new_image = PlaceImage(
                        place_id=place_id,
                        url=url,
                        is_primary=(url == primary_url),
                        confidence=score,
                    )

                    db.add(new_image)

                    written.append(new_image)

                except Exception as exc:

                    logger.debug(
                        "image_materialize_entry_failed place_id=%s error=%s",
                        place_id,
                        exc,
                    )

            if primary_url:
                self._enforce_single_primary(
                    db=db,
                    place_id=place_id,
                    primary_url=primary_url,
                )

            db.flush()

            logger.info(
                "image_materialize_complete place_id=%s written=%s",
                place_id,
                len(written),
            )

            return written

        except Exception as exc:

            logger.exception(
                "image_materialize_failed place_id=%s error=%s",
                place_id,
                exc,
            )

            return []

    # ---------------------------------------------------------
    # Existing images
    # ---------------------------------------------------------

    def _existing_images(
        self,
        *,
        db: Session,
        place_id: str,
    ) -> List[PlaceImage]:

        stmt = select(PlaceImage).where(
            PlaceImage.place_id == place_id
        )

        return list(db.execute(stmt).scalars().all())

    # ---------------------------------------------------------
    # Primary enforcement
    # ---------------------------------------------------------

    def _enforce_single_primary(
        self,
        *,
        db: Session,
        place_id: str,
        primary_url: str,
    ) -> None:

        stmt = select(PlaceImage).where(
            PlaceImage.place_id == place_id
        )

        images = db.execute(stmt).scalars().all()

        for image in images:

            if image.url == primary_url:
                image.is_primary = True
            else:
                image.is_primary = False

        if images:
            images[0].created_at = images[0].created_at or _utcnow()