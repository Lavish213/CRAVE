from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


# =========================================================
# Map Place (Pin Data)
# =========================================================

class MapPlace(BaseModel):
    """
    Minimal place representation for map pins.

    Optimized for:
        • map rendering
        • clustering
        • viewport queries
    """

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: str
    name: str = Field(..., min_length=1)

    lat: float
    lng: float

    city_id: str
    price_tier: Optional[int] = Field(default=None, ge=1, le=4)

    rank_score: float = Field(..., ge=0.0, le=1.0)

    primary_image_url: Optional[str] = None


# =========================================================
# Map Center
# =========================================================

class MapCenter(BaseModel):

    model_config = ConfigDict(frozen=True)

    lat: float
    lng: float


# =========================================================
# Map Response
# =========================================================

class MapResponse(BaseModel):
    """
    Response payload for map queries.
    """

    model_config = ConfigDict(frozen=True)

    ok: bool

    center: MapCenter

    radius_km: float = Field(..., ge=0)
    limit: int = Field(..., ge=1)
    count: int = Field(..., ge=0)

    places: List[MapPlace]


# --- GeoJSON types (Mapbox FeatureCollection) ---


class GeoJSONProperties(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    city_id: Optional[str] = None
    tier: str  # elite | trusted | solid | default
    rank_score: float = Field(..., ge=0.0)
    price_tier: Optional[int] = Field(default=None, ge=1, le=4)
    primary_image_url: Optional[str] = None
    has_menu: bool = False


class GeoJSONGeometry(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: str = "Point"
    coordinates: list[float]  # [lng, lat] — Mapbox standard


class GeoJSONFeature(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: str = "Feature"
    geometry: GeoJSONGeometry
    properties: GeoJSONProperties


class GeoJSONFeatureCollection(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: str = "FeatureCollection"
    features: List[GeoJSONFeature]