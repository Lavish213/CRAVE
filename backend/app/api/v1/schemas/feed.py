from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict

from app.api.v1.schemas.place_card import PlaceCardOut


class FeedMeta(BaseModel):

    model_config = ConfigDict(frozen=True)

    city_id: Optional[str] = Field(
        default=None,
        description="City context used for the feed",
    )

    limit: int = Field(
        ...,
        ge=1,
        le=200,
        description="Number of results returned",
    )


class FeedResponse(BaseModel):

    model_config = ConfigDict(frozen=True)

    items: List[PlaceCardOut] = Field(default_factory=list)

    meta: FeedMeta