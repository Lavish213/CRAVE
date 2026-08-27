"""
decision_session.py -- Decision Session, Phase 1 narrow slice.

Same candidate-retrieval Layer 1 as places.py (radius near / city bucket
/ global rank_score), so a Decision Session pick is always drawn from
the same pool Feed itself would show for the same location -- see
docs/decision_session_spec.md.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.services.query.places_query import list_places as query_list_places
from app.services.query.proximity_query import list_places_near
from app.services.feed.feed_bucket_manager import get_feed_places
from app.services.query.place_image_visibility_query import get_primary_image_urls_bulk
from app.services.query.rank_percentile_query import get_rank_percentiles
from app.services.decision_session.decision_session_builder import build_decision_session
from app.api.v1.schemas.decision_session import DecisionSessionCardOut, DecisionSessionOut
from app.api.v1.schemas.places import PlaceOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/decision-session", tags=["decision-session"])

_DEFAULT_RADIUS_MILES = 20.0
_MIN_RADIUS_MILES = 0.25
_MAX_RADIUS_MILES = 50.0
# Wide enough candidate pool for rank_feed's diversity + this route's own
# category-distinctness requirement to have real room to work with --
# same multiplier logic places.py's city-bucket path already uses.
_CANDIDATE_POOL_SIZE = 80


@router.get(
    "",
    response_model=DecisionSessionOut,
    summary="3-card decision set: best fit / safe bet / wildcard",
    dependencies=[Depends(rate_limit)],
)
def get_decision_session(
    city_id: Optional[str] = Query(None, description="City UUID — optional; omit for global"),
    lat: Optional[float] = Query(None, description="User latitude"),
    lng: Optional[float] = Query(None, description="User longitude"),
    radius_miles: float = Query(
        _DEFAULT_RADIUS_MILES, ge=_MIN_RADIUS_MILES, le=_MAX_RADIUS_MILES,
    ),
    db: Session = Depends(get_db),
) -> DecisionSessionOut:
    has_location = lat is not None and lng is not None

    try:
        if has_location:
            candidates, _total = list_places_near(
                db=db, lat=lat, lng=lng, radius_miles=radius_miles,
                limit=_CANDIDATE_POOL_SIZE, offset=0,
            )
        elif city_id:
            try:
                candidates, _total = get_feed_places(db=db, city_id=city_id, limit=_CANDIDATE_POOL_SIZE)
            except Exception as feed_exc:
                logger.warning("decision_session_feed_mixer_failed city_id=%s error=%s", city_id, feed_exc)
                candidates, _total = query_list_places(db=db, city_id=city_id, limit=_CANDIDATE_POOL_SIZE, offset=0)
        else:
            candidates, _total = query_list_places(db=db, city_id=None, limit=_CANDIDATE_POOL_SIZE, offset=0)
    except Exception as exc:
        logger.exception(
            "decision_session_query_failed city_id=%s lat=%s lng=%s error=%s",
            city_id, lat, lng, exc,
        )
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")

    place_ids = [p.id for p in candidates]
    rank_percentiles = get_rank_percentiles(db, place_ids=place_ids)

    built_cards = build_decision_session(candidates, rank_percentiles=rank_percentiles, lat=lat, lng=lng)

    image_urls = get_primary_image_urls_bulk(db, place_ids=[c.place.id for c in built_cards])

    cards = []
    for c in built_cards:
        try:
            c.place.primary_image_url = image_urls.get(c.place.id)
            c.place.rank_percentile = rank_percentiles.get(c.place.id)
            cards.append(
                DecisionSessionCardOut(
                    place=PlaceOut.model_validate(c.place, from_attributes=True),
                    role=c.role,
                    reason_codes=c.reason_codes,
                )
            )
        except Exception as exc:
            # Same silent-drop hazard already fixed in places.py/recommendations.py
            # -- a place failing PlaceOut validation must be visible, not
            # just quietly absent from the response.
            logger.exception("decision_session_serialize_failed place_id=%s", getattr(c.place, "id", None))

    logger.info(
        "API_RESPONSE endpoint=/decision-session city_id=%s lat=%s lng=%s roles=%s",
        city_id, lat, lng, [c.role for c in cards],
    )

    return DecisionSessionOut(cards=cards, degraded=len(cards) < 3)
