from __future__ import annotations

from typing import List
from pydantic import BaseModel, ConfigDict, Field


# =========================================================
# Category Output
# =========================================================

class CategoryOut(BaseModel):
    """
    Public category representation.

    Used by:
        • /categories
        • UI filters
        • onboarding flows
    """

    model_config = ConfigDict(
        from_attributes=True,
        frozen=True,
    )

    id: str
    name: str = Field(..., min_length=1)

    icon: str | None = None
    color: str | None = None


# =========================================================
# Categories Response
# =========================================================

class CategoriesResponse(BaseModel):
    """
    Category collection response.

    Deterministic ordering handled upstream.
    """

    model_config = ConfigDict(
        frozen=True,
    )

    total: int = Field(..., ge=0)

    items: List[CategoryOut] = Field(default_factory=list)