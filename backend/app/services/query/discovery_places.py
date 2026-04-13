# FILE: backend/app/services/query/discovery_places.py

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session, load_only

from app.db.models.place import Place
from app.db.models.place_image import PlaceImage


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