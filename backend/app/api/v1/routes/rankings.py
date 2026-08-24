# app/api/v1/routes/rankings.py
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.session import get_db
from app.db.models.place import Place
from app.db.models.user_profile import UserProfile
from app.services.personal_ranking import ranking_service
from app.services.personal_ranking.ranking_service import RankingError
from app.services.query.place_image_visibility_query import get_primary_image_urls_bulk
from app.services.social.activity_service import record_ranked_place

router = APIRouter(prefix="/rankings", tags=["rankings"])


class StartRankingRequest(BaseModel):
    place_id: str
    tier: str
    visited_at: Optional[datetime] = None
    note: Optional[str] = None
    tags: Optional[List[str]] = None


class CompareRequest(BaseModel):
    comparison_token: str
    winner: str


class RankingOut(BaseModel):
    place_id: str
    tier: str
    rank_score: float
    note: Optional[str]
    tags: Optional[List[str]]
    visited_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class RankedPlaceOut(RankingOut):
    """
    A ranking plus enough of its place to render a list row. Without the
    denormalized name/image here, a profile showing N ranked places would
    cost N extra round trips from mobile just to turn ids into something
    displayable — see get_primary_image_urls_bulk usage below.
    """

    name: Optional[str] = None
    primary_image_url: Optional[str] = None
    city_id: Optional[str] = None


def _hydrate_rankings(db: Session, rankings: list) -> List[RankedPlaceOut]:
    """Attach place name/image/category in two bulk queries, not N+1."""
    if not rankings:
        return []

    place_ids = [r.place_id for r in rankings]
    places = {
        p.id: p for p in db.query(Place).filter(Place.id.in_(place_ids)).all()
    }
    image_urls = get_primary_image_urls_bulk(db, place_ids=list(places.keys()))

    out: List[RankedPlaceOut] = []
    for r in rankings:
        place = places.get(r.place_id)
        row = RankedPlaceOut.model_validate(r)
        if place:
            row = row.model_copy(update={
                "name": place.name,
                "primary_image_url": image_urls.get(place.id),
                "city_id": place.city_id,
            })
        out.append(row)
    return out


def _serialize_result(result: dict) -> dict:
    if result["status"] == "ranked":
        return {"status": "ranked", "ranking": RankingOut.model_validate(result["ranking"])}
    return {
        "status": "comparing",
        "comparison_token": result["comparison_token"],
        "opponent_place_id": result["opponent_place_id"],
    }


@router.post("", status_code=201, dependencies=[Depends(rate_limit), Depends(require_api_key)])
def start_ranking(
    payload: StartRankingRequest = Body(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        result = ranking_service.start_ranking(
            db, user_id=user_id, place_id=payload.place_id, tier=payload.tier,
            visited_at=payload.visited_at, note=payload.note, tags=payload.tags,
        )
    except RankingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if result["status"] == "ranked":
        record_ranked_place(
            db, user_id=user_id, place_id=payload.place_id,
            tier=payload.tier, score=result["ranking"].rank_score,
        )
        db.commit()

    return _serialize_result(result)


@router.post("/compare", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def submit_comparison(
    payload: CompareRequest = Body(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        result = ranking_service.submit_comparison(
            db, token=payload.comparison_token, winner=payload.winner, expected_user_id=user_id,
        )
    except RankingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # already_existed=True means this call landed on a replay of an
    # already-fully-processed final comparison (see ranking_service's
    # IntegrityError handling) -- the activity event and any other
    # first-time-only side effects were already recorded when the
    # original request succeeded, and recording them again here would
    # duplicate them for no reason other than a network retry.
    if result["status"] == "ranked" and not result.get("already_existed"):
        ranking = result["ranking"]
        record_ranked_place(
            db, user_id=ranking.user_id, place_id=ranking.place_id,
            tier=ranking.tier, score=ranking.rank_score,
        )
        db.commit()

    return _serialize_result(result)


@router.get("/me", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def get_my_rankings(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return {"rankings": _hydrate_rankings(db, ranking_service.list_user_rankings(db, user_id))}


@router.get("/user/{target_user_id}", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def get_user_rankings(
    target_user_id: str,
    db: Session = Depends(get_db),
    _user_id: str = Depends(get_current_user_id),
):
    """Someone else's ranked list — the thing a profile page is actually for."""
    profile = (
        db.query(UserProfile).filter(UserProfile.id == target_user_id).one_or_none()
    )
    if not profile or not profile.is_public:
        raise HTTPException(status_code=404, detail="profile not found")

    return {
        "rankings": _hydrate_rankings(db, ranking_service.list_user_rankings(db, target_user_id))
    }


@router.delete("/{place_id}", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def delete_ranking(
    place_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    deleted = ranking_service.delete_ranking(db, user_id=user_id, place_id=place_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="ranking not found")
    return {"status": "deleted"}
