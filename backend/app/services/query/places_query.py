from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.db.models.place_image import PlaceImage


logger = logging.getLogger(__name__)


DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def _clamp_limit(limit: int) -> int:
    try:
        limit = int(limit)
    except Exception:
        return DEFAULT_LIMIT

    return max(1, min(MAX_LIMIT, limit))


def _clamp_offset(offset: int) -> int:
    try:
        offset = int(offset)
    except Exception:
        return 0

    return max(0, offset)


def list_places(
    db: Session,
    *,
    city_id: Optional[str] = None,
    category_id: Optional[str] = None,
    price_tier: Optional[int] = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> Tuple[List[Place], int]:

    limit = _clamp_limit(limit)
    offset = _clamp_offset(offset)

    try:
        query = db.query(Place)

        # ✅ SAFE: only apply if column exists AND has real values
        if hasattr(Place, "is_active"):
            query = query.filter(Place.is_active.is_(True))

        if city_id:
            query = query.filter(Place.city_id == str(city_id))

        if price_tier is not None:
            try:
                query = query.filter(Place.price_tier == int(price_tier))
            except Exception:
                pass

        if category_id:
            try:
                query = query.join(Place.categories).filter_by(id=category_id)
            except Exception as exc:
                logger.debug("places_category_filter_failed error=%s", exc)

        total = query.count()

        results = (
            query.order_by(
                Place.rank_score.desc(),
                Place.id.asc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

        return results or [], total

    except Exception as exc:
        logger.exception("list_places_failed error=%s", exc)
        return [], 0


def get_place(
    db: Session,
    place_id: str,
) -> Optional[Place]:
    if not place_id:
        return None

    try:
        query = db.query(Place).filter(Place.id == place_id)

        if hasattr(Place, "is_active"):
            query = query.filter(Place.is_active.is_(True))

        return query.one_or_none()

    except Exception as exc:
        logger.exception("get_place_failed place_id=%s error=%s", place_id, exc)
        return None


def get_primary_image(
    db: Session,
    place_id: str,
) -> Optional[str]:
    if not place_id:
        return None

    try:
        img = (
            db.query(PlaceImage)
            .filter(
                PlaceImage.place_id == place_id,
                PlaceImage.is_primary.is_(True),
            )
            .order_by(
                PlaceImage.created_at.desc(),
                PlaceImage.id.asc(),
            )
            .first()
        )

        return getattr(img, "url", None)

    except Exception as exc:
        logger.exception(
            "get_primary_image_failed place_id=%s error=%s",
            place_id,
            exc,
        )
        return None