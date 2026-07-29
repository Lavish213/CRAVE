"""
Centralized visibility query layer for place images.

ALL image queries for public surfaces must go through this module.
NO filtering logic in routes.

Surfaces:
  public_gallery  — visible images for place detail / gallery UI
  primary_image   — single best primary for a place
  internal        — all images including hidden (admin / invariant checks)
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.db.models.place_image import (
    PlaceImage,
    VISIBILITY_HIDDEN,
)


# ---------------------------------------------------------------------------
# Public gallery
# ---------------------------------------------------------------------------

def get_public_gallery(
    db: Session,
    *,
    place_id: str,
    limit: int = 9,
) -> List[PlaceImage]:
    """
    Returns all non-hidden images for a place, primary first.

    Used by: place detail endpoint, gallery UI.
    Phase 2 enforcement: visibility_status != hidden is the gate.
    """
    stmt = (
        select(PlaceImage)
        .where(
            PlaceImage.place_id == place_id,
            PlaceImage.visibility_status != VISIBILITY_HIDDEN,
        )
        .order_by(
            PlaceImage.is_primary.desc(),
            PlaceImage.confidence.desc(),
            PlaceImage.created_at.desc(),
            PlaceImage.id.asc(),
        )
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


# ---------------------------------------------------------------------------
# Primary image
# ---------------------------------------------------------------------------

def get_primary_image(
    db: Session,
    *,
    place_id: str,
) -> Optional[PlaceImage]:
    """
    Returns the single primary image for a place.
    Must not be hidden (hard invariant).

    Returns None if no valid primary exists.
    """
    stmt = (
        select(PlaceImage)
        .where(
            PlaceImage.place_id == place_id,
            PlaceImage.is_primary.is_(True),
            PlaceImage.visibility_status != VISIBILITY_HIDDEN,
        )
        .order_by(
            PlaceImage.confidence.desc(),
            PlaceImage.created_at.desc(),
            PlaceImage.id.asc(),
        )
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def get_primary_image_url(
    db: Session,
    *,
    place_id: str,
) -> Optional[str]:
    """Returns the URL of the primary image or None."""
    img = get_primary_image(db, place_id=place_id)
    return img.url if img else None


# ---------------------------------------------------------------------------
# Primary image subquery (for use in larger queries, e.g. map)
# ---------------------------------------------------------------------------

def primary_image_url_subquery():
    """
    SQLAlchemy scalar subquery: returns the primary image URL for a place.
    Hidden images are excluded.

    Usage:
        from app.services.query.place_image_visibility_query import primary_image_url_subquery
        from app.db.models.place import Place

        subq = primary_image_url_subquery()
        q = db.query(Place.id, subq.correlate(Place).label("primary_image_url"))
    """
    from app.db.models.place import Place  # local import to avoid circular

    return (
        select(PlaceImage.url)
        .where(
            and_(
                PlaceImage.place_id == Place.id,
                PlaceImage.is_primary.is_(True),
                PlaceImage.visibility_status != VISIBILITY_HIDDEN,
            )
        )
        .order_by(
            PlaceImage.confidence.desc(),
            PlaceImage.created_at.desc(),
            PlaceImage.id.asc(),
        )
        .limit(1)
        .scalar_subquery()
    )


# ---------------------------------------------------------------------------
# Bulk primary image lookup (visibility-gated)
# ---------------------------------------------------------------------------

def get_primary_image_urls_bulk(
    db: Session,
    *,
    place_ids: List[str],
) -> dict:
    """
    Bulk-fetch primary image URLs for a list of place IDs.
    Excludes hidden images — safe for all public surfaces.

    Returns: {place_id: proxy_url}
    """
    import re
    import urllib.parse

    _GOOGLE_PHOTO_RE = re.compile(
        r"places\.googleapis\.com/v1/(places/[^/]+/photos/[^/?]+)"
    )

    def _to_proxy_url(url):
        if not url:
            return None
        if url.startswith("places/"):
            return f"/api/v1/image?ref={url}"
        m = _GOOGLE_PHOTO_RE.search(url)
        if m:
            return f"/api/v1/image?ref={m.group(1)}"
        return url

    if not place_ids:
        return {}

    stmt = (
        select(
            PlaceImage.place_id,
            PlaceImage.url,
            PlaceImage.created_at,
            PlaceImage.id,
        )
        .where(
            PlaceImage.place_id.in_(place_ids),
            PlaceImage.is_primary.is_(True),
            PlaceImage.visibility_status != VISIBILITY_HIDDEN,
        )
        .order_by(
            PlaceImage.place_id.asc(),
            PlaceImage.confidence.desc(),
            PlaceImage.created_at.desc(),
            PlaceImage.id.asc(),
        )
    )

    rows = db.execute(stmt).all()

    picked: dict = {}
    for place_id, url, _created_at, _id in rows:
        if place_id not in picked:
            proxy = _to_proxy_url(url)
            if proxy:
                picked[place_id] = proxy
        if len(picked) == len(place_ids):
            break

    return picked


# ---------------------------------------------------------------------------
# Internal (admin / invariant checks only)
# ---------------------------------------------------------------------------

def get_all_images(
    db: Session,
    *,
    place_id: str,
) -> List[PlaceImage]:
    """
    Returns ALL images including hidden. Admin / invariant use only.
    NEVER expose this to public API surfaces.
    """
    stmt = (
        select(PlaceImage)
        .where(PlaceImage.place_id == place_id)
        .order_by(
            PlaceImage.is_primary.desc(),
            PlaceImage.confidence.desc(),
            PlaceImage.id.asc(),
        )
    )
    return list(db.execute(stmt).scalars().all())
