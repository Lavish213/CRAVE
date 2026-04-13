from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.place_image import PlaceImage


def get_primary_image_url(
    db: Session,
    *,
    place_id: str,
) -> Optional[str]:

    if not place_id:
        return None

    stmt = (
        select(PlaceImage.url)
        .where(
            PlaceImage.place_id == place_id,
            PlaceImage.is_primary.is_(True),
        )
        .order_by(
            PlaceImage.created_at.desc(),
            PlaceImage.id.asc(),
        )
        .limit(1)
    )

    return db.execute(stmt).scalar_one_or_none()


def get_primary_image_urls_bulk(
    db: Session,
    *,
    place_ids: List[str],
) -> Dict[str, str]:

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
        )
        .order_by(
            PlaceImage.place_id.asc(),
            PlaceImage.created_at.desc(),
            PlaceImage.id.asc(),
        )
    )

    rows = db.execute(stmt).all()

    picked: Dict[str, str] = {}

    for place_id, url, _created_at, _id in rows:

        if place_id not in picked:
            picked[place_id] = url

        if len(picked) == len(place_ids):
            break

    return picked