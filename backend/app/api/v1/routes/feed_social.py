# app/api/v1/routes/feed_social.py
"""
The friend activity feed — "your friend just ranked X" — distinct from
places.py's algorithmic /feed (which orders the catalog itself). This one
is purely social: it's empty until you follow people.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.session import get_db
from app.services.social import follow_service
from app.services.social.activity_service import list_friend_feed

router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("/friends", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def get_friends_feed(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    followee_ids = follow_service.list_following(db, user_id, limit=500, offset=0)
    events = list_friend_feed(db, follower_ids=followee_ids, limit=limit, offset=offset)

    return {
        "events": [
            {
                "id": e.id,
                "user_id": e.user_id,
                "event_type": e.event_type,
                "place_id": e.place_id,
                "target_user_id": e.target_user_id,
                "payload": e.payload,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ]
    }
