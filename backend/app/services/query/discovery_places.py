# FILE: backend/app/services/query/discovery_places.py

from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session, load_only

from app.db.models.place import Place
from app.db.models.place_image import PlaceImage


def list_discovery_places(
    db: Session,
    *,
    city_id: Optional[str] = None,
    limit: int = 50,
) -> List[Place]:
    """
    Return recently-added active places for feed discovery mixing.
    Ordered by created_at DESC so freshest places surface first.
    """
    try:
        limit = max(1, min(200, int(limit)))
    except Exception:
        limit = 50

    query = db.query(Place).filter(Place.is_active.is_(True))
    if city_id:
        query = query.filter(Place.city_id == str(city_id))

    return (
        query.order_by(Place.created_at.desc())
        .limit(limit)
        .all()
    )


def get_place(
    db: Session,
    place_id: str,
) -> Optional[Place]:

    place_id = (place_id or "").strip()
    if not place_id:
        return None

    return (
        db.query(Place)
        .options(
            load_only(
                Place.id,
                Place.name,
                Place.city_id,
                Place.rank_score,
            )
        )
        .filter(
            Place.id == place_id,
            Place.is_active.is_(True),
        )
        .first()
    )


def get_primary_image(
    db: Session,
    place_id: str,
) -> Optional[str]:

    place_id = (place_id or "").strip()
    if not place_id:
        return None

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

    return img.url if img and img.url else None