from __future__ import annotations

from typing import List

from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.schemas.place_card import PlaceCardOut


class SearchResponse(BaseModel):

    model_config = ConfigDict(
        frozen=True,
    )

    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)

    items: List[PlaceCardOut] = Field(default_factory=list)