from __future__ import annotations

import re
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.place_image import PlaceImage


_GOOGLE_PHOTO_RE = re.compile(
    r"places\.googleapis\.com/v1/(places/[^/]+/photos/[^/?]+)"
)


def _to_proxy_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    if url.startswith("places/"):
        return f"/api/image?ref={url}"
    m = _GOOGLE_PHOTO_RE.search(url)
    if m:
        return f"/api/image?ref={m.group(1)}"
    return url


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

    url = db.execute(stmt).scalar_one_or_none()
    return _to_proxy_url(url)


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
            proxy = _to_proxy_url(url)
            if proxy:
                picked[place_id] = proxy

        if len(picked) == len(place_ids):
            break

    return picked
