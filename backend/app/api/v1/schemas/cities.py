from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


# =========================================================
# City Output
# =========================================================

class CityOut(BaseModel):
    """
    Public city representation.

    Used by:
    • /cities
    • map filters
    • onboarding
    """

    model_config = ConfigDict(
        from_attributes=True,
        frozen=True,
    )

    id: str
    name: str = Field(..., min_length=1)
    slug: str | None = None
    lat: Optional[float] = None
    lng: Optional[float] = None


# =========================================================
# Cities Response
# =========================================================

class CitiesResponse(BaseModel):
    """
    Collection response for cities.
    """

    model_config = ConfigDict(
        frozen=True,
    )

    total: int = Field(..., ge=0)

    items: List[CityOut] = Field(default_factory=list)