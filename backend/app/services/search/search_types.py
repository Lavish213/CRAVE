from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SearchResult:
    place_id: str
    name: str
    city_id: str
    rank_score: float
    lat: Optional[float] = None
    lng: Optional[float] = None
    price_tier: Optional[int] = None
    has_menu: bool = False


@dataclass
class SearchResponse:
    results: List[SearchResult] = field(default_factory=list)
    total: int = 0
    query: str = ""
    page: int = 1
    page_size: int = 20
