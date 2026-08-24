# app/api/v1/routes/follows.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.session import get_db
from app.services.social import follow_service
from app.services.social.activity_service import record_followed_user

router = APIRouter(prefix="/follows", tags=["follows"])


@router.post("/{target_user_id}", status_code=201, dependencies=[Depends(rate_limit), Depends(require_api_key)])
def follow(
    target_user_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        _follow, created = follow_service.follow_user(db, follower_id=user_id, followee_id=target_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Only a genuinely new follow gets an activity event -- a retry of an
    # already-successful follow (request landed, response lost) must not
    # duplicate "so-and-so followed you" in every follower's feed.
    if created:
        record_followed_user(db, user_id=user_id, target_user_id=target_user_id)
        db.commit()
    return {"status": "following"}


@router.delete("/{target_user_id}", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def unfollow(
    target_user_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    follow_service.unfollow_user(db, follower_id=user_id, followee_id=target_user_id)
    return {"status": "not_following"}


@router.get("/status/{target_user_id}", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def follow_status(
    target_user_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return {
        "following": follow_service.is_following(db, follower_id=user_id, followee_id=target_user_id),
        "followed_by": follow_service.is_following(db, follower_id=target_user_id, followee_id=user_id),
    }


@router.get("/following", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def get_following(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return {"user_ids": follow_service.list_following(db, user_id, limit=limit, offset=offset)}


@router.get("/followers", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def get_followers(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return {"user_ids": follow_service.list_followers(db, user_id, limit=limit, offset=offset)}
