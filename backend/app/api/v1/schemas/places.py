from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_GENERIC_CATEGORIES = {"restaurant", "restaurants", "bar", "bars", "other", "others", ""}
# "Other" and blank are truly meaningless — never return as category label
_VOID_CATEGORIES = {"other", "others", ""}

# Tier thresholds — mirrors scoring.ts getTier()
def _rank_to_tier(score: float) -> str:
    if score >= 0.42: return "crave_pick"
    if score >= 0.32: return "gem"
    if score >= 0.22: return "solid"
    return "new"


# =========================================================
# Place Output Schema
# =========================================================

class PlaceOut(BaseModel):
    """
    Canonical feed/search place representation.

    Includes all fields required by feed cards:
    id, name, lat, lng, distance_miles, tier, rank_score,
    category, price_tier, primary_image_url, address, website,
    has_menu, grubhub_url.
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

    # Computed by feed_ranker.rank_feed() and injected as ORM attribute
    distance_miles: Optional[float] = None

    price_tier: Optional[int] = Field(default=None, ge=1, le=4)

    rank_score: float = Field(..., ge=0.0, le=1.0)

    # Computed from rank_score — mirrors scoring.ts getTier()
    tier: str = "new"

    primary_image_url: Optional[str] = None

    categories: List[str] = Field(default_factory=list)

    # First non-generic category name. Populated by _inject_category.
    category: Optional[str] = None

    address: Optional[str] = None
    website: Optional[str] = None
    grubhub_url: Optional[str] = None
    has_menu: bool = False

    @model_validator(mode="before")
    @classmethod
    def _inject_category(cls, data):
        """
        Populate `category` from the first non-generic entry in `categories`,
        and compute `tier` and `distance_miles` from ORM attributes.
        Handles both dict and ORM-object inputs (Pydantic from_attributes=True).
        """
        def _cat_name(c) -> str:
            return (getattr(c, "name", None) or str(c) or "").strip()

        def _first_specific(cats) -> Optional[str]:
            """First non-generic category name (e.g. Japanese, BBQ)."""
            for c in cats:
                name = _cat_name(c)
                if name and name.lower() not in _GENERIC_CATEGORIES:
                    return name
            return None

        def _best_category(cats) -> Optional[str]:
            """
            Best available category label, never null unless no category exists.

            Priority:
              1. First specific (e.g. Japanese, Pizza)
              2. First non-void generic (e.g. Restaurant, Bar) — informative fallback
              3. None — only when place has zero categories or only "Other"/""
            """
            specific = _first_specific(cats)
            if specific:
                return specific
            # Fallback: first non-void category name
            for c in cats:
                name = _cat_name(c)
                if name and name.lower() not in _VOID_CATEGORIES:
                    return name
            return None

        if isinstance(data, dict):
            cats = data.get("categories") or []
            if cats and not data.get("category"):
                data["category"] = _best_category(cats)
            if not data.get("tier"):
                data["tier"] = _rank_to_tier(float(data.get("rank_score") or 0.0))
        else:
            # ORM object — build a plain dict for Pydantic
            cats = getattr(data, "categories", None) or []
            rank = float(getattr(data, "rank_score", None) or 0.0)
            return {
                "id": getattr(data, "id", None),
                "name": getattr(data, "name", None),
                "city_id": getattr(data, "city_id", None),
                "lat": getattr(data, "lat", None),
                "lng": getattr(data, "lng", None),
                "distance_miles": getattr(data, "distance_miles", None),
                "price_tier": getattr(data, "price_tier", None),
                "rank_score": rank,
                "tier": _rank_to_tier(rank),
                "primary_image_url": getattr(data, "primary_image_url", None),
                "categories": cats,
                "category": _best_category(cats),
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
            if not name or name.lower() in _GENERIC_CATEGORIES or name in seen:
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
    # Upper bound capped at 500 (saves endpoint max); feed pages are always ≤ 40 in practice.
    page_size: int = Field(..., ge=1, le=500)

    items: List[PlaceOut] = Field(default_factory=list)