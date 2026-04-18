"""
User saves (bookmarks) — place_id based.

Piggybacks on hitlist_saves table using dedup_key = "save:{user_id}:{place_id}".
This keeps saves separate from the craves-discovery flow (which uses url/place_name dedup keys).

Routes:
    POST   /saves              create save
    DELETE /saves/{place_id}   remove save
    GET    /saves              list saved places with full PlaceOut data
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.db.session import get_db
from app.db.models.hitlist_save import HitlistSave
from app.db.models.place import Place
from app.api.v1.schemas.places import PlaceOut, PlacesResponse
from app.services.query.place_image_query import get_primary_image_urls_bulk

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/saves", tags=["saves"])

_DEDUP_PREFIX = "save"


def _dedup_key(user_id: str, place_id: str) -> str:
    return f"{_DEDUP_PREFIX}:{user_id}:{place_id}"


# -------------------------------------------------------
# Request schemas
# -------------------------------------------------------

class SaveRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    place_id: str = Field(..., min_length=1, max_length=36)


# -------------------------------------------------------
# POST /saves — create save
# -------------------------------------------------------

@router.post("", status_code=201)
def create_save(
    payload: SaveRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_api_key),
) -> dict:
    dedup = _dedup_key(payload.user_id, payload.place_id)

    # Idempotent: already saved → return existing
    existing = (
        db.query(HitlistSave)
        .filter(
            HitlistSave.user_id == payload.user_id,
            HitlistSave.dedup_key == dedup,
        )
        .one_or_none()
    )
    if existing:
        logger.debug("save_already_exists user_id=%s place_id=%s", payload.user_id, payload.place_id)
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
        user_id=payload.user_id,
        place_name=place.name,
        place_id=payload.place_id,
        resolution_status="resolved",
        dedup_key=dedup,
    )
    db.add(save)
    db.commit()

    logger.info("save_created user_id=%s place_id=%s place_name=%s", payload.user_id, payload.place_id, place.name)
    return {"status": "saved", "id": save.id}


# -------------------------------------------------------
# DELETE /saves/{place_id} — remove save
# -------------------------------------------------------

@router.delete("/{place_id}", status_code=200)
def delete_save(
    place_id: str,
    user_id: str = Query(..., min_length=1, max_length=128),
    db: Session = Depends(get_db),
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

@router.get("", response_model=PlacesResponse)
def list_saves(
    user_id: str = Query(..., min_length=1, max_length=128),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
    _: None = Depends(require_api_key),
) -> PlacesResponse:
    """
    Return saved places for a user, ordered newest-first.
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
        return PlacesResponse(total=0, page=1, page_size=limit, items=[])

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

    items = []
    for save in saves:
        p = place_map.get(save.place_id)
        if not p:
            continue
        try:
            p.primary_image_url = image_urls.get(p.id)
            items.append(PlaceOut.model_validate(p, from_attributes=True))
        except Exception as exc:
            logger.debug("saves_serialize_failed place_id=%s error=%s", p.id, exc)

    logger.info(
        "API_RESPONSE endpoint=/saves user_id=%s count=%s",
        user_id, len(items),
    )
    return PlacesResponse(total=len(items), page=1, page_size=limit, items=items)
