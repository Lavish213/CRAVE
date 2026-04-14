# app/api/v1/schemas/hitlist.py
from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class HitlistSaveRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    place_name: str = Field(..., min_length=1, max_length=256)
    source_url: Optional[str] = Field(None, max_length=1024)
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lng: Optional[float] = Field(None, ge=-180, le=180)


class HitlistSuggestRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    place_name: str = Field(..., min_length=1, max_length=256)
    source_url: Optional[str] = Field(None, max_length=1024)
    city_hint: Optional[str] = Field(None, max_length=128)


class HitlistItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    place_name: str
    source_platform: Optional[str] = None
    source_url: Optional[str] = None
    place_id: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    resolution_status: str
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


class HitlistResponse(BaseModel):
    items: List[HitlistItemOut]
    total: int


class HitlistSuggestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    place_name: str
    source_platform: Optional[str] = None
    created_at: Optional[datetime] = None
