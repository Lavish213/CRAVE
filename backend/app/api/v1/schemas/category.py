from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List


# =========================================================
# Category Output Schema
# =========================================================

class CategoryOut(BaseModel):
    """
    Public category representation.

    Categories are global taxonomy entries used for:
    - search filters
    - map filtering
    - place tagging
    """

    id: str = Field(..., description="Deterministic category UUID")
    name: str = Field(..., description="Human readable category name")
    slug: str = Field(..., description="URL-safe category identifier")

    class Config:
        from_attributes = True


# =========================================================
# Categories Response Wrapper
# =========================================================

class CategoriesResponse(BaseModel):
    """
    Wrapper response used by the /categories endpoint.

    A wrapper keeps the API extensible without
    breaking clients if metadata is added later.
    """

    categories: List[CategoryOut]