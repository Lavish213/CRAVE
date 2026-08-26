from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class RecommendationEventIn(BaseModel):
    """
    Deliberately permissive (every field optional, no ge/le/enum
    constraints) -- a single malformed event must fail validation as
    "this one event gets dropped", handled in
    recommendation_event_service.build_valid_events(), never as "the
    whole batch request 422s". A strict field constraint here would
    make that impossible: Pydantic validates the full request body
    atomically, so one bad event would take down every other real event
    in the same batch.
    """

    place_id: Optional[str] = None
    surface: Optional[str] = None
    event_type: Optional[str] = None
    position: Optional[int] = None
    rank_percentile: Optional[float] = None
    query: Optional[str] = None
    city_id: Optional[str] = None
    session_id: Optional[str] = None
    # Idempotency key for a confirmed save/unsave outcome -- see
    # RecommendationEvent.client_event_id's own docstring. Absent from
    # every impression/click (those have no retry path to dedupe).
    client_event_id: Optional[str] = None
    # A stable interaction-session id, scoped to whatever `surface` this
    # event belongs to -- see RecommendationEvent.search_session_id's own
    # docstring for why this one column now serves both Search and Map
    # despite the name.
    search_session_id: Optional[str] = None


class RecommendationEventBatchIn(BaseModel):
    events: List[RecommendationEventIn] = Field(default_factory=list)


class RecommendationEventBatchOut(BaseModel):
    accepted: int
