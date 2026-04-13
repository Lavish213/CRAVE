from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


# =========================================================
# Place Output Schema
# =========================================================

class PlaceOut(BaseModel):
    """
    Standard place representation returned by search.

    Designed for:
    • search results
    • simple place lists
    • lightweight responses

    Deterministic fields
    --------------------
    • no ranking logic
    • no mutation
    • read-only schema
    """

    model_config = ConfigDict(
        from_attributes=True,
        frozen=True,
    )

    id: str
    name: str = Field(..., min_length=1)
    city_id: str

    lat: Optional[float] = None
    lng: Optional[float] = None

    price_tier: Optional[int] = Field(default=None, ge=1, le=4)

    rank_score: float = Field(..., ge=0.0, le=1.0)

    primary_image_url: Optional[str] = None

    categories: List[str] = Field(default_factory=list)


# =========================================================
# Paginated Places Response
# =========================================================

class PlacesResponse(BaseModel):
    """
    Standard paginated response for /places endpoint.

    Guarantees
    ----------
    • deterministic response structure
    • stable pagination
    • immutable schema
    """

    model_config = ConfigDict(frozen=True)

    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)

    items: List[PlaceOut] = Field(default_factory=list)