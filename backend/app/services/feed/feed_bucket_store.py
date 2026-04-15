from __future__ import annotations
import time
from threading import RLock
from typing import Dict, Optional
from .feed_bucket_types import FeedBucket

_store: Dict[str, FeedBucket] = {}
_lock = RLock()
_BUCKET_TTL_SECONDS = 300  # 5 minutes


def get_bucket(key: str) -> Optional[FeedBucket]:
    with _lock:
        bucket = _store.get(key)
        if bucket is None:
            return None
        if time.time() - bucket.generated_at > _BUCKET_TTL_SECONDS:
            del _store[key]
            return None
        return bucket


def set_bucket(key: str, bucket: FeedBucket) -> None:
    with _lock:
        _store[key] = bucket


def bucket_key(city_id: str | None) -> str:
    return city_id or "global"


def invalidate_bucket(city_id: str | None) -> None:
    key = bucket_key(city_id)
    with _lock:
        _store.pop(key, None)
