from __future__ import annotations
import time
from typing import Dict, Optional
from .feed_bucket_types import FeedBucket

_store: Dict[str, FeedBucket] = {}

_BUCKET_TTL_SECONDS = 300  # 5 minutes


def get_bucket(key: str) -> Optional[FeedBucket]:
    bucket = _store.get(key)
    if bucket is None:
        return None
    if time.time() - bucket.generated_at > _BUCKET_TTL_SECONDS:
        del _store[key]
        return None
    return bucket

def set_bucket(key: str, bucket: FeedBucket) -> None:
    _store[key] = bucket

def bucket_key(city_id: str | None) -> str:
    return city_id or "global"
