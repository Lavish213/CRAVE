from __future__ import annotations
import time
from typing import Dict, Optional
from .feed_bucket_types import FeedBucket

_store: Dict[str, FeedBucket] = {}

def get_bucket(key: str) -> Optional[FeedBucket]:
    return _store.get(key)

def set_bucket(key: str, bucket: FeedBucket) -> None:
    _store[key] = bucket

def bucket_key(city_id: str | None) -> str:
    return city_id or "global"
