"""
places_query.py — City/Global Candidate Retrieval

Retrieves Place candidates by rank_score for city or global feed.
This is Layer 1 (retrieval) only.

All ranking, blending, and diversity belong in feed_ranker.rank_feed().
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.db.models.place_image import PlaceImage


logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 50
MAX_LIMIT = 200

# Fetch pool multiplier: give rank_feed enough candidates to diversify well
_POOL_MULTIPLIER = 4


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
    """
    Retrieve active places ordered by rank_score DESC.

    Returns a candidate pool sized at limit*4 on page 1 so the calling
    route can pass results through feed_ranker.rank_feed() for blended
    scoring and diversity.

    Pagination (offset > 0) returns exactly `limit` results in rank order
    (diversity only applies on page 1 when the ranker is called).
    """
    limit = _clamp_limit(limit)
    offset = _clamp_offset(offset)

    try:
        query = db.query(Place)

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

        # On page 1: fetch a generous pool for rank_feed to work with.
        # On subsequent pages: fetch exactly what was requested.
        fetch_limit = min(limit * _POOL_MULTIPLIER, MAX_LIMIT) if not offset else limit

        results = (
            query.order_by(Place.rank_score.desc(), Place.id.asc())
            .offset(offset)
            .limit(fetch_limit)
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
        logger.exception("get_primary_image_failed place_id=%s error=%s", place_id, exc)
        return None
