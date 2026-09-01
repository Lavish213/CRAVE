"""
User saves (bookmarks) — place_id based.

Piggybacks on hitlist_saves table using dedup_key = "save:{user_id}:{place_id}".
This keeps saves separate from the craves-discovery flow (which uses url/place_name dedup keys).

Routes:
    POST   /saves                  create save
    DELETE /saves/{place_id}       remove save
    GET    /saves                  list saved places with full PlaceOut data
                                    plus per-save memory (visited/notes)
    PATCH  /saves/{place_id}/memory  update visited/notes for one save
    GET    /saves/map              saved places as GeoJSON, for the Map
                                    tab's "my places" layer
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.core.user_auth import get_current_user_id
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.db.models.hitlist_save import HitlistSave
from app.db.models.place import Place
from app.api.v1.schemas.places import PlaceOut
from app.api.v1.schemas.map import GeoJSONFeatureCollection
from app.services.query.place_image_visibility_query import get_primary_image_urls_bulk
from app.services.query.place_video_visibility_query import get_has_video_bulk
from app.services.query.saved_places_map_query import get_saved_places_geojson

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/saves", tags=["saves"])

_DEDUP_PREFIX = "save"


def _dedup_key(user_id: str, place_id: str) -> str:
    return f"{_DEDUP_PREFIX}:{user_id}:{place_id}"


# -------------------------------------------------------
# Request schemas
# -------------------------------------------------------

class SaveRequest(BaseModel):
    # user_id intentionally NOT a field here — it comes from the verified
    # bearer token (get_current_user_id), never from the client. Accepting
    # it from the request body was the app's core IDOR bug: any caller could
    # save/delete/list on behalf of any other user by passing their UUID.
    place_id: str = Field(..., min_length=1, max_length=36)


class SaveMemoryRequest(BaseModel):
    """
    PATCH body for /saves/{place_id}/memory. Both fields optional and
    independently settable — `exclude_unset` on read distinguishes "not
    provided" from "explicitly cleared" (notes: null), matching normal
    PATCH semantics. `visited_at` is never client-settable; it's derived
    server-side from `visited`.
    """
    visited: Optional[bool] = None
    notes: Optional[str] = Field(default=None, max_length=2000)


class SavedPlaceOut(PlaceOut):
    """
    PlaceOut plus this user's per-save memory (E2). Only used by
    GET /saves — every other PlaceOut consumer (Feed/Search/Map/
    Trending/Decision Session) is untouched, so this stays additive to
    /saves alone rather than widening the shared card contract.
    """
    visited: bool = False
    visited_at: Optional[datetime] = None
    notes: Optional[str] = None


class SavedPlacesResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[SavedPlaceOut] = Field(default_factory=list)


# -------------------------------------------------------
# POST /saves — create save
# -------------------------------------------------------

@router.post("", status_code=201, dependencies=[Depends(rate_limit)])
def create_save(
    payload: SaveRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    _: None = Depends(require_api_key),
) -> dict:
    dedup = _dedup_key(user_id, payload.place_id)

    # Idempotent: already saved → return existing
    existing = (
        db.query(HitlistSave)
        .filter(
            HitlistSave.user_id == user_id,
            HitlistSave.dedup_key == dedup,
        )
        .one_or_none()
    )
    if existing:
        logger.debug("save_already_exists user_id=%s place_id=%s", user_id, payload.place_id)
        return {"status": "already_saved", "id": existing.id}

    # Verify place exists and is active
    place = db.execute(
        select(Place).where(
            Place.id == payload.place_id,
            Place.is_active.is_(True),
        )
    ).scalar_one_or_none()

    if not place:
        raise HTTPException(status_code=404, detail="Place not found")

    save = HitlistSave(
        id=str(uuid.uuid4()),
        user_id=user_id,
        place_name=place.name,
        place_id=payload.place_id,
        resolution_status="resolved",
        dedup_key=dedup,
    )
    db.add(save)
    db.commit()

    logger.info("save_created user_id=%s place_id=%s place_name=%s", user_id, payload.place_id, place.name)
    return {"status": "saved", "id": save.id}


# -------------------------------------------------------
# DELETE /saves/{place_id} — remove save
# -------------------------------------------------------

@router.delete("/{place_id}", status_code=200, dependencies=[Depends(rate_limit)])
def delete_save(
    place_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    _: None = Depends(require_api_key),
) -> dict:
    dedup = _dedup_key(user_id, place_id)

    save = (
        db.query(HitlistSave)
        .filter(
            HitlistSave.user_id == user_id,
            HitlistSave.dedup_key == dedup,
        )
        .one_or_none()
    )

    if not save:
        raise HTTPException(status_code=404, detail="Save not found")

    db.delete(save)
    db.commit()

    logger.info("save_deleted user_id=%s place_id=%s", user_id, place_id)
    return {"status": "deleted"}


# -------------------------------------------------------
# GET /saves — list saved places
# -------------------------------------------------------

@router.get("", response_model=SavedPlacesResponse, dependencies=[Depends(rate_limit)])
def list_saves(
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    _: None = Depends(require_api_key),
) -> SavedPlacesResponse:
    """
    Return saved places for a user, ordered newest-first, each carrying
    this user's visited/notes memory for that save (E2).
    Only returns app-created saves (dedup_key starts with 'save:').
    """
    saves = (
        db.query(HitlistSave)
        .filter(
            HitlistSave.user_id == user_id,
            HitlistSave.place_id.isnot(None),
            HitlistSave.dedup_key.like(f"{_DEDUP_PREFIX}:%"),
        )
        .order_by(HitlistSave.created_at.desc())
        .limit(limit)
        .all()
    )

    place_ids = [s.place_id for s in saves if s.place_id]

    if not place_ids:
        return SavedPlacesResponse(total=0, page=1, page_size=limit, items=[])

    # Preserve save order in the result
    place_map = {
        p.id: p
        for p in db.execute(
            select(Place).where(
                Place.id.in_(place_ids),
                Place.is_active.is_(True),
            )
        ).scalars().all()
    }

    image_urls = get_primary_image_urls_bulk(db, place_ids=list(place_map.keys()))
    video_flags = get_has_video_bulk(db, place_ids=list(place_map.keys()))

    items = []
    for save in saves:
        p = place_map.get(save.place_id)
        if not p:
            continue
        try:
            p.primary_image_url = image_urls.get(p.id)
            p.has_video = video_flags.get(p.id, False)
            base = PlaceOut.model_validate(p, from_attributes=True)
            items.append(
                SavedPlaceOut(
                    **base.model_dump(),
                    visited=save.visited,
                    visited_at=save.visited_at,
                    notes=save.notes,
                )
            )
        except Exception as exc:
            logger.debug("saves_serialize_failed place_id=%s error=%s", p.id, exc)

    logger.info(
        "API_RESPONSE endpoint=/saves user_id=%s count=%s",
        user_id, len(items),
    )
    return SavedPlacesResponse(total=len(items), page=1, page_size=limit, items=items)


# -------------------------------------------------------
# PATCH /saves/{place_id}/memory — set visited / notes (E2)
# -------------------------------------------------------

@router.patch("/{place_id}/memory", status_code=200, dependencies=[Depends(rate_limit)])
def update_save_memory(
    place_id: str,
    payload: SaveMemoryRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    _: None = Depends(require_api_key),
) -> dict:
    dedup = _dedup_key(user_id, place_id)

    save = (
        db.query(HitlistSave)
        .filter(
            HitlistSave.user_id == user_id,
            HitlistSave.dedup_key == dedup,
        )
        .one_or_none()
    )

    if not save:
        raise HTTPException(status_code=404, detail="Save not found")

    fields = payload.model_dump(exclude_unset=True)

    if "visited" in fields:
        save.visited = bool(fields["visited"])
        save.visited_at = datetime.now(timezone.utc) if save.visited else None

    if "notes" in fields:
        save.notes = fields["notes"]

    db.commit()

    logger.info(
        "save_memory_updated user_id=%s place_id=%s visited=%s has_notes=%s",
        user_id, place_id, save.visited, save.notes is not None,
    )
    return {
        "status": "updated",
        "visited": save.visited,
        "visited_at": save.visited_at,
        "notes": save.notes,
    }


# -------------------------------------------------------
# GET /saves/map — saved places as GeoJSON, for the Map tab's "my
# places" layer (Beli/Biter's "your own curated map," which the global
# catalog view on the Map tab never provided).
# -------------------------------------------------------

@router.get(
    "/map",
    response_model=GeoJSONFeatureCollection,
    dependencies=[Depends(rate_limit), Depends(require_api_key)],
)
def get_saved_places_map(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> GeoJSONFeatureCollection:
    result = get_saved_places_geojson(db, user_id=user_id)
    logger.info(
        "API_RESPONSE endpoint=/saves/map user_id=%s count=%s",
        user_id, len(result.get("features", [])),
    )
    return GeoJSONFeatureCollection.model_validate(result)
