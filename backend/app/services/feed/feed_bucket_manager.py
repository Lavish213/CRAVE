from __future__ import annotations
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from app.db.models.place import Place
from app.services.feed.feed_bucket_store import (
    get_bucket,
    set_bucket,
    bucket_key,
)
from app.services.feed.feed_bucket_builder import build_bucket

def get_feed_places(
    db: Session,
    *,
    city_id: Optional[str],
    limit: int = 30,
) -> Tuple[List[Place], int]:

    key = bucket_key(city_id)

    bucket = get_bucket(key)

    if bucket is None:

        bucket = build_bucket(
            db,
            city_id=city_id,
        )

        set_bucket(key, bucket)

    total = len(bucket.place_ids)
    ids = bucket.place_ids[:limit]

    if not ids:
        return [], total

    places = (
        db.query(Place)
        .filter(Place.id.in_(ids))
        .all()
    )

    place_map = {p.id: p for p in places}

    ordered = [place_map[i] for i in ids if i in place_map]

    return ordered, total
