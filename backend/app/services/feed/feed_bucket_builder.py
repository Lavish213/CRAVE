from __future__ import annotations
import time
from typing import List
from sqlalchemy.orm import Session
from app.db.models.place import Place
from app.services.query.places_query import list_places
from app.services.query.discovery_places import list_discovery_places
from app.services.query.feed_mixer import mix_feed
from .feed_bucket_types import FeedBucket

def build_bucket(
    db: Session,
    *,
    city_id: str | None,
    limit: int = 200,
) -> FeedBucket:

    stable = list_places(
        db,
        city_id=city_id,
        limit=limit * 2,
    )

    discovery = list_discovery_places(
        db,
        city_id=city_id,
        limit=limit,
    )

    places: List[Place] = mix_feed(
        stable_places=stable,
        discovery_places=discovery,
        limit=limit,
    )

    ids = [p.id for p in places]

    return FeedBucket(
        city_id=city_id,
        place_ids=ids,
        generated_at=time.time(),
    )
