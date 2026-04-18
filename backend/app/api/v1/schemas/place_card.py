from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_GENERIC = {"restaurant", "restaurants", "bar", "bars", "other", "others", ""}
_VOID = {"other", "others", ""}  # Never return these as category label


# -----------------------------------------------------
# BASE CARD (INTERNAL USE)
# -----------------------------------------------------

class PlaceCard(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        frozen=True,
    )

    id: str
    name: str
    city_id: str

    lat: Optional[float] = None
    lng: Optional[float] = None

    price_tier: Optional[int] = Field(default=None, ge=1, le=4)

    rank_score: float = 0.0
    master_score: float = 0.0
    confidence_score: float = 0.0
    operational_confidence: float = 0.0
    local_validation: float = 0.0

    primary_image: Optional[str] = None
    categories: List[str] = Field(default_factory=list)

    # safety normalization
    @field_validator("name")
    @classmethod
    def _clean_name(cls, v: str) -> str:
        return (v or "").strip()

    @field_validator("categories", mode="before")
    @classmethod
    def _clean_categories(cls, v) -> List[str]:
        seen = set()
        cleaned: List[str] = []

        for c in v or []:
            # Handle Category ORM objects and plain strings
            name = (getattr(c, "name", None) or str(c) or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            cleaned.append(name)

        return cleaned


# -----------------------------------------------------
# PUBLIC RESPONSE MODEL
# -----------------------------------------------------

class PlaceCardOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        frozen=True,
    )

    id: str
    name: str = Field(..., min_length=1)
    city_id: str

    lat: Optional[float] = None
    lng: Optional[float] = None

    address: Optional[str] = None
    website: Optional[str] = None
    grubhub_url: Optional[str] = None
    has_menu: bool = False

    price_tier: Optional[int] = Field(default=None, ge=1, le=4)

    rank_score: float = Field(default=0.0, ge=0.0)
    master_score: float = Field(default=0.0, ge=0.0)
    confidence_score: float = Field(default=0.0, ge=0.0)
    operational_confidence: float = Field(default=0.0, ge=0.0)
    local_validation: float = Field(default=0.0, ge=0.0)

    primary_image_url: Optional[str] = None
    primary_image: Optional[str] = None  # alias used by search route
    categories: List[str] = Field(default_factory=list)
    category: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v: str) -> str:
        v = (v or "").strip()
        return v if v else "Unknown"

    @field_validator("categories", mode="before")
    @classmethod
    def _clean_categories(cls, v) -> List[str]:
        seen: set = set()
        cleaned: List[str] = []
        for c in v or []:
            name = (getattr(c, "name", None) or str(c) or "").strip()
            if not name or name.lower() in _GENERIC or name in seen:
                continue
            seen.add(name)
            cleaned.append(name)
        return cleaned

    @model_validator(mode="before")
    @classmethod
    def _inject_category(cls, data):
        """Derive category from ORM categories list when not already set."""
        def _cat_name(c) -> str:
            return (getattr(c, "name", None) or str(c) or "").strip()

        if not isinstance(data, dict):
            # ORM object path
            cats = getattr(data, "categories", None) or []
            # First: specific non-generic
            category = None
            for c in cats:
                name = _cat_name(c)
                if name and name.lower() not in _GENERIC:
                    category = name
                    break
            # Fallback: first non-void (e.g. "Restaurant" is OK)
            if not category:
                for c in cats:
                    name = _cat_name(c)
                    if name and name.lower() not in _VOID:
                        category = name
                        break
            return {
                "id": getattr(data, "id", None),
                "name": getattr(data, "name", None),
                "city_id": getattr(data, "city_id", None),
                "lat": getattr(data, "lat", None),
                "lng": getattr(data, "lng", None),
                "address": getattr(data, "address", None),
                "website": getattr(data, "website", None),
                "grubhub_url": getattr(data, "grubhub_url", None),
                "has_menu": getattr(data, "has_menu", False),
                "price_tier": getattr(data, "price_tier", None),
                "rank_score": float(getattr(data, "rank_score", None) or 0.0),
                "master_score": float(getattr(data, "master_score", None) or 0.0),
                "confidence_score": float(getattr(data, "confidence_score", None) or 0.0),
                "operational_confidence": float(getattr(data, "operational_confidence", None) or 0.0),
                "local_validation": float(getattr(data, "local_validation", None) or 0.0),
                "primary_image_url": getattr(data, "primary_image_url", None),
                "primary_image": getattr(data, "primary_image", None),
                "categories": cats,
                "category": category,
            }
        # Dict path: populate category if missing
        if not data.get("category") and data.get("categories"):
            cats = data["categories"]
            for c in cats:
                name = _cat_name(c)
                if name and name.lower() not in _GENERIC:
                    data["category"] = name
                    break
            if not data.get("category"):
                for c in cats:
                    name = _cat_name(c)
                    if name and name.lower() not in _VOID:
                        data["category"] = name
                        break
        return data


# -----------------------------------------------------
# RESPONSE WRAPPER
# -----------------------------------------------------

class PlaceCardsResponse(BaseModel):
    model_config = ConfigDict(
        frozen=True,
    )

    total: int = Field(default=0, ge=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)

    items: List[PlaceCardOut] = Field(default_factory=list)