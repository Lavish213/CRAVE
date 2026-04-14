from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import exists, func, not_, or_, select
from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.db.models.place_image import PlaceImage
from app.services.images.image_ingest_service import ImageIngestService


logger = logging.getLogger(__name__)

UTC = timezone.utc

DEFAULT_BATCH_SIZE = 50
MAX_BATCH_SIZE = 200

MIN_IMAGE_COUNT = 3
STALE_IMAGE_DAYS = 30


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ImageWorker:
    """
    Production image ingestion worker.

    Responsibilities
    ----------------
    - select places that need image ingestion
    - backfill places with no images
    - refresh places with too few images
    - refresh places with missing primary image
    - refresh stale image galleries
    - support forced refresh and targeted place ids
    - isolate failures per place
    - keep processing deterministic and bounded
    """

    def __init__(
        self,
        *,
        ingest_service: Optional[ImageIngestService] = None,
    ) -> None:
        self.ingest_service = ingest_service or ImageIngestService()

    # ---------------------------------------------------------
    # Worker entrypoint
    # ---------------------------------------------------------

    def run(
        self,
        *,
        db: Session,
        limit: int = DEFAULT_BATCH_SIZE,
        force_refresh: bool = False,
        place_ids: Optional[List[str]] = None,
    ) -> Dict[str, int]:

        limit = self._normalize_limit(limit)

        places = self._select_places(
            db=db,
            limit=limit,
            force_refresh=force_refresh,
            place_ids=place_ids,
        )

        if not places:

            logger.info(
                "image_worker_no_places force_refresh=%s limit=%s",
                force_refresh,
                limit,
            )

            return {
                "processed": 0,
                "succeeded": 0,
                "failed": 0,
                "images_written": 0,
            }

        logger.info(
            "image_worker_start places=%s force_refresh=%s limit=%s",
            len(places),
            force_refresh,
            limit,
        )

        processed = 0
        succeeded = 0
        failed = 0
        images_written = 0

        for place in places:

            processed += 1

            try:

                images = self.ingest_service.ingest_place_images(
                    db=db,
                    place=place,
                    force_refresh=force_refresh,
                )

                db.commit()

                succeeded += 1
                images_written += len(images)

                logger.debug(
                    "image_worker_place_complete place_id=%s images=%s",
                    getattr(place, "id", None),
                    len(images),
                )

            except Exception as exc:

                db.rollback()

                failed += 1

                logger.exception(
                    "image_worker_place_failed place_id=%s error=%s",
                    getattr(place, "id", None),
                    exc,
                )

        result = {
            "processed": processed,
            "succeeded": succeeded,
            "failed": failed,
            "images_written": images_written,
        }

        logger.info(
            "image_worker_complete processed=%s succeeded=%s failed=%s images_written=%s",
            processed,
            succeeded,
            failed,
            images_written,
        )

        return result

    # ---------------------------------------------------------
    # Place selection logic
    # ---------------------------------------------------------

    def _select_places(
        self,
        *,
        db: Session,
        limit: int,
        force_refresh: bool,
        place_ids: Optional[List[str]],
    ) -> List[Place]:

        stmt = select(Place).where(
            Place.is_active.is_(True),
        )

        if place_ids:
            stmt = stmt.where(Place.id.in_(place_ids))

        if not force_refresh:
            stmt = stmt.where(self._needs_image_work_clause())

        stmt = stmt.order_by(
            Place.rank_score.desc(),
            Place.confidence_score.desc(),
            Place.created_at.asc(),
        ).limit(limit)

        return list(db.execute(stmt).scalars().all())

    def _needs_image_work_clause(self):
        """
        Select places that need image work:
        - no images at all, OR
        - fewer than MIN_IMAGE_COUNT images, OR
        - no primary image set

        Stale refresh (images older than STALE_IMAGE_DAYS) is NOT selected
        here — it requires explicit force_refresh=True to avoid wasting
        Google API calls on places that already have acceptable images.
        """
        total_images_subquery = (
            select(func.count(PlaceImage.id))
            .where(PlaceImage.place_id == Place.id)
            .scalar_subquery()
        )

        primary_exists_clause = exists(
            select(PlaceImage.id).where(
                PlaceImage.place_id == Place.id,
                PlaceImage.is_primary.is_(True),
            )
        )

        any_images_clause = exists(
            select(PlaceImage.id).where(
                PlaceImage.place_id == Place.id,
            )
        )

        return or_(
            not_(any_images_clause),
            total_images_subquery < MIN_IMAGE_COUNT,
            not_(primary_exists_clause),
        )

    # ---------------------------------------------------------
    # Limit guard
    # ---------------------------------------------------------

    def _normalize_limit(
        self,
        limit: int,
    ) -> int:

        try:
            limit = int(limit)
        except Exception:
            return DEFAULT_BATCH_SIZE

        if limit <= 0:
            return DEFAULT_BATCH_SIZE

        if limit > MAX_BATCH_SIZE:
            return MAX_BATCH_SIZE

        return limit