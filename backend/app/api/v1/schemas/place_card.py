from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    price_tier: Optional[int] = Field(default=None, ge=1, le=4)

    rank_score: float = Field(default=0.0, ge=0.0)
    master_score: float = Field(default=0.0, ge=0.0)
    confidence_score: float = Field(default=0.0, ge=0.0)
    operational_confidence: float = Field(default=0.0, ge=0.0)
    local_validation: float = Field(default=0.0, ge=0.0)

    primary_image: Optional[str] = None
    categories: List[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v: str) -> str:
        v = (v or "").strip()
        return v if v else "Unknown"

    @field_validator("categories", mode="before")
    @classmethod
    def _clean_categories(cls, v) -> List[str]:
        seen = set()
        cleaned: List[str] = []

        for c in v or []:
            name = (getattr(c, "name", None) or str(c) or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            cleaned.append(name)

        return cleaned


# -----------------------------------------------------
# RESPONSE WRAPPER
# -----------------------------------------------------

class PlaceCardsResponse(BaseModel):
    model_config = ConfigDict(
        frozen=True,
    )

    total: int = Field(default=0, ge=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)

    items: List[PlaceCardOut] = Field(default_factory=list)