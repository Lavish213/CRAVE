from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.schemas.place_card import PlaceCardOut


class SearchInterpretationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    original_query: str
    lookup_query: str
    price_tier: Optional[int] = Field(default=None, ge=1, le=4)
    required_categories: List[str] = Field(default_factory=list)
    hard_constraints: List[str] = Field(default_factory=list)
    unsupported_hard_constraints: List[str] = Field(default_factory=list)
    context: List[str] = Field(default_factory=list)
    uncertain: bool = False


class SearchResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    items: List[PlaceCardOut] = Field(default_factory=list)
    interpretation: SearchInterpretationOut
    exact_match_id: Optional[str] = None
    relaxed_constraints: List[str] = Field(default_factory=list)
