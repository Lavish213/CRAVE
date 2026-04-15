from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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

    # Singular convenience field — first category name, or None.
    # Populated by _inject_category before freezing.
    category: Optional[str] = None

    # Fields missing from the original schema
    address: Optional[str] = None
    website: Optional[str] = None
    grubhub_url: Optional[str] = None
    has_menu: bool = False

    @model_validator(mode="before")
    @classmethod
    def _inject_category(cls, data):
        """
        Populate `category` from the first entry in `categories` before
        the model is constructed (and frozen).

        Pydantic v2 with from_attributes=True passes the ORM object directly
        here, so we handle both dict and ORM-object inputs.
        """
        if isinstance(data, dict):
            cats = data.get("categories") or []
            if cats and not data.get("category"):
                first = cats[0]
                name = (getattr(first, "name", None) or str(first) or "").strip()
                if name:
                    data["category"] = name
        else:
            # ORM object — build a plain dict so Pydantic can finish construction
            cats = getattr(data, "categories", None) or []
            first_name: Optional[str] = None
            if cats:
                first = cats[0]
                raw = (getattr(first, "name", None) or str(first) or "").strip()
                first_name = raw or None

            return {
                "id": getattr(data, "id", None),
                "name": getattr(data, "name", None),
                "city_id": getattr(data, "city_id", None),
                "lat": getattr(data, "lat", None),
                "lng": getattr(data, "lng", None),
                "price_tier": getattr(data, "price_tier", None),
                "rank_score": getattr(data, "rank_score", None),
                "primary_image_url": getattr(data, "primary_image_url", None),
                "categories": cats,
                "category": first_name,
                "address": getattr(data, "address", None),
                "website": getattr(data, "website", None),
                "grubhub_url": getattr(data, "grubhub_url", None),
                "has_menu": getattr(data, "has_menu", False),
            }
        return data

    @field_validator("categories", mode="before")
    @classmethod
    def _clean_categories(cls, v) -> List[str]:
        seen: set = set()
        cleaned: List[str] = []
        for c in v or []:
            name = (getattr(c, "name", None) or str(c) or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            cleaned.append(name)
        return cleaned


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