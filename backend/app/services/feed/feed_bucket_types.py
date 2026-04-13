from __future__ import annotations
from typing import List
from dataclasses import dataclass

@dataclass(frozen=True)
class FeedBucket:
    city_id: str | None
    place_ids: List[str]
    generated_at: float
