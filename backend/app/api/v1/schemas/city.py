from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List


# =========================================================
# City Output Schema
# =========================================================
class CityOut(BaseModel):
    """
    Public city representation.
    This is intentionally minimal and stable because
    cities are referenced across multiple surfaces
    (map, search filters, onboarding, etc.).
    """
    id: str = Field(..., description="Deterministic city UUID")
    name: str = Field(..., description="Display name of the city")
    slug: str = Field(..., description="URL-safe city identifier")

    class Config:
        from_attributes = True
# =========================================================
# Cities Response Wrapper
# =========================================================
class CitiesResponse(BaseModel):
    """
    Wrapper response used by the /cities endpoint.

    Returning a wrapper keeps the response extensible
    (pagination, metadata, etc.) without breaking clients.
    """
    cities: List[CityOut]