# FILE: backend/app/api/v1/routes/recommendations.py
"""
Personalized recommendations -- Beli's "prediction score" feed. See
app.services.social.recommendation_service for the actual collaborative-
filtering algorithm; this route is a thin wrapper, same shape as
trending.py (same PlaceOut/PlacesResponse response model, same bulk
image lookup), so the frontend can reuse its existing place-list
rendering rather than needing a bespoke response shape.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id, get_current_user_id_optional
from app.db.session import get_db
from app.api.v1.schemas.places import PlaceOut, PlacesResponse
from app.api.v1.schemas.recommendation_event import (
    RecommendationEventBatchIn,
    RecommendationEventBatchOut,
)
from app.services.query.place_image_visibility_query import get_primary_image_urls_bulk
from app.services.query.place_video_visibility_query import get_has_video_bulk
from app.services.recommendations.recommendation_event_service import (
    MAX_BATCH_SIZE,
    record_events,
)
from app.services.social.recommendation_service import get_recommendations

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get(
    "",
    response_model=PlacesResponse,
    summary="Personalized place recommendations",
    dependencies=[Depends(rate_limit), Depends(require_api_key)],
)
def get_recommendations_route(
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> PlacesResponse:
    places = get_recommendations(db, user_id=user_id, limit=limit)

    place_ids = [p.id for p in places]
    image_urls = get_primary_image_urls_bulk(db, place_ids=place_ids)
    video_flags = get_has_video_bulk(db, place_ids=place_ids)

    items = []
    for p in places:
        try:
            p.primary_image_url = image_urls.get(p.id)
            p.has_video = video_flags.get(p.id, False)
            items.append(PlaceOut.model_validate(p, from_attributes=True))
        except Exception:
            # Was logger.debug -- invisible at the app's default INFO
            # level, same silent-drop shape confirmed live in /search and
            # /places (see rank_percentile_query.py's fix): a place
            # failing PlaceOut validation vanishes from the response with
            # zero operational signal. logger.exception logs at ERROR
            # with the full traceback.
            logger.exception("recommendations_serialize_failed place_id=%s", p.id)

    return PlacesResponse(total=len(items), page=1, page_size=limit, items=items)


@router.post(
    "/events",
    response_model=RecommendationEventBatchOut,
    summary="Log a batch of recommendation impression/click/save/rank events",
    dependencies=[Depends(rate_limit), Depends(require_api_key)],
)
def record_recommendation_events(
    payload: RecommendationEventBatchIn,
    db: Session = Depends(get_db),
    user_id: Optional[str] = Depends(get_current_user_id_optional),
) -> RecommendationEventBatchOut:
    if len(payload.events) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Too many events in one batch (max {MAX_BATCH_SIZE})",
        )

    submitted = len(payload.events)
    accepted = record_events(db, raw_events=payload.events, user_id=user_id)
    # Deliberately INFO, not DEBUG: this is the only signal that the
    # Ledger is actually receiving real data post-deploy short of
    # querying the table directly. rejected > 0 on a healthy client
    # build would mean a real bug (a surface/event_type typo, a stale
    # app version) -- not just noise to be filtered out.
    logger.info(
        "recommendation_events_ingested submitted=%s accepted=%s rejected=%s user=%s",
        submitted, accepted, submitted - accepted, "anon" if user_id is None else "known",
    )
    return RecommendationEventBatchOut(accepted=accepted)
