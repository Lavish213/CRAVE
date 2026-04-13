from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel


# ---------------------------------------------------------
# Place Image
# ---------------------------------------------------------

class PlaceImageOut(BaseModel):
    url: str
    is_primary: bool

    class Config:
        from_attributes = True


# ---------------------------------------------------------
# Category
# ---------------------------------------------------------

class PlaceCategoryOut(BaseModel):
    id: str
    name: str
    icon: Optional[str] = None
    color: Optional[str] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------
# Place Detail
# ---------------------------------------------------------

class PlaceDetail(BaseModel):
    id: str
    name: str
    city_id: str

    lat: Optional[float] = None
    lng: Optional[float] = None

    price_tier: Optional[int] = None

    # Final discovery ranking
    rank_score: float

    # Relationships
    categories: List[PlaceCategoryOut] = []
    images: List[PlaceImageOut] = []

    class Config:
        from_attributes = True