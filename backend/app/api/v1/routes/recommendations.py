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

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.session import get_db
from app.api.v1.schemas.places import PlaceOut, PlacesResponse
from app.services.query.place_image_visibility_query import get_primary_image_urls_bulk
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

    items = []
    for p in places:
        try:
            p.primary_image_url = image_urls.get(p.id)
            items.append(PlaceOut.model_validate(p, from_attributes=True))
        except Exception as exc:
            logger.debug("recommendations_serialize_failed place_id=%s error=%s", p.id, exc)

    return PlacesResponse(total=len(items), page=1, page_size=limit, items=items)
