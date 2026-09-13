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
from app.db.models.place import Place
from app.db.models.user_profile import UserProfile
from app.services.query.place_image_visibility_query import get_primary_image_urls_bulk
from app.services.social import follow_service
from app.services.social.activity_service import list_friend_feed, list_user_activity

router = APIRouter(prefix="/feed", tags=["feed"])


def _hydrate_events(db: Session, events):
    """Attach only the public display fields the activity UI can render."""
    if not events:
        return {"events": []}

    actor_ids = {e.user_id for e in events} | {
        e.target_user_id for e in events if e.target_user_id
    }
    profiles = {
        p.id: p
        for p in db.query(UserProfile).filter(UserProfile.id.in_(actor_ids)).all()
    }
    place_ids = [e.place_id for e in events if e.place_id]
    places = {
        p.id: p for p in db.query(Place).filter(Place.id.in_(place_ids)).all()
    } if place_ids else {}
    image_urls = get_primary_image_urls_bulk(db, place_ids=list(places.keys())) if places else {}

    def _actor(uid: str | None) -> dict | None:
        if not uid:
            return None
        profile = profiles.get(uid)
        if not profile:
            return {"id": uid, "username": None, "display_name": None, "avatar_url": None}
        return {
            "id": profile.id,
            "username": profile.username,
            "display_name": profile.display_name,
            "avatar_url": profile.avatar_url,
        }

    return {"events": [{
        "id": event.id,
        "user_id": event.user_id,
        "actor": _actor(event.user_id),
        "event_type": event.event_type,
        "place_id": event.place_id,
        "place_name": places[event.place_id].name if event.place_id in places else None,
        "place_image_url": image_urls.get(event.place_id) if event.place_id else None,
        "target_user_id": event.target_user_id,
        "target_user": _actor(event.target_user_id),
        "payload": event.payload,
        "created_at": event.created_at.isoformat(),
    } for event in events]}


@router.get("/activity", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def get_my_activity(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    events = list_user_activity(db, user_id=user_id, limit=limit, offset=offset)
    return _hydrate_events(db, events)


@router.get("/friends", dependencies=[Depends(rate_limit), Depends(require_api_key)])
def get_friends_feed(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    followee_ids = follow_service.list_following(db, user_id, limit=500, offset=0)
    events = list_friend_feed(db, follower_ids=followee_ids, limit=limit, offset=offset)

    return _hydrate_events(db, events)
