from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.query.places_query import list_places as query_list_places
from app.services.query.proximity_query import list_places_near
from app.services.feed.feed_bucket_manager import get_feed_places
from app.services.feed.feed_ranker import rank_feed
from app.services.query.place_image_query import get_primary_image_urls_bulk
from app.api.v1.schemas.places import PlacesResponse, PlaceOut
from app.db.models.menu_item import MenuItem
from app.db.models.place import Place

from app.services.cache.response_cache import response_cache
from app.services.cache.cache_keys import feed_key
from app.services.cache.cache_ttl import feed_ttl
from app.core.rate_limit import rate_limit


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/places",
    tags=["places"],
)

_DEFAULT_RADIUS_MILES = 20.0
_MIN_RADIUS_MILES = 0.25
_MAX_RADIUS_MILES = 50.0


@router.get(
    "",
    response_model=PlacesResponse,
    summary="List ranked places",
)
def get_places(
    city_id: Optional[str] = Query(None, description="City UUID — optional; omit for global feed"),
    lat: Optional[float] = Query(None, description="User latitude"),
    lng: Optional[float] = Query(None, description="User longitude"),
    radius_miles: float = Query(
        _DEFAULT_RADIUS_MILES,
        ge=_MIN_RADIUS_MILES,
        le=_MAX_RADIUS_MILES,
        description="Search radius in miles (default 20, max 50)",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit),
) -> PlacesResponse:
    """
    Return ranked places using the layered feed pipeline.

    Feed pipeline:
      Layer 1 — Candidate retrieval (SQL bounding box or rank_score)
      Layer 2 — Ranking via feed_ranker.rank_feed()
               score = rank×0.65 + prox×0.20 + quality×0.10 + explore×0.05
      Layer 3 — Greedy window-constrained diversity in rank_feed

    Priority:
      1. lat/lng → radius-based proximity feed
      2. city_id → city feed
      3. Neither  → global top by rank_score
    """
    has_location = lat is not None and lng is not None

    cache_key = feed_key(
        city_id=city_id or (f"geo:{round(lat,3)},{round(lng,3)}:{radius_miles}" if has_location else "global"),
        page=page,
        page_size=page_size,
    )

    try:
        cached = response_cache.get(cache_key)
        if cached is not None:
            return cached
    except Exception as exc:
        logger.debug("places_cache_read_failed error=%s", exc)

    offset = (page - 1) * page_size

    # ── Layer 1: Candidate Retrieval ──────────────────────────────────────────
    try:
        if has_location:
            # Radius-based proximity candidates
            candidates, total = list_places_near(
                db=db,
                lat=lat,
                lng=lng,
                radius_miles=radius_miles,
                limit=page_size,
                offset=offset,
            )
            # Auto-expand radius once when proximity pool is too thin
            if offset == 0 and len(candidates) < max(page_size // 2, 5):
                expanded_radius = min(radius_miles * 2, _MAX_RADIUS_MILES)
                if expanded_radius > radius_miles:
                    logger.info(
                        "places_radius_expand lat=%s lng=%s from=%.1f to=%.1f candidates=%s",
                        lat, lng, radius_miles, expanded_radius, len(candidates),
                    )
                    candidates, total = list_places_near(
                        db=db,
                        lat=lat,
                        lng=lng,
                        radius_miles=expanded_radius,
                        limit=page_size,
                        offset=offset,
                    )
        elif city_id and page == 1:
            # City feed mixer (fast-path with pre-built bucket)
            try:
                candidates, total = get_feed_places(db=db, city_id=city_id, limit=page_size * 4)
            except Exception as feed_exc:
                logger.warning("feed_mixer_failed city_id=%s error=%s", city_id, feed_exc)
                candidates, total = query_list_places(
                    db=db, city_id=city_id, limit=page_size, offset=offset
                )
        else:
            # Global or city feed with rank_score retrieval
            candidates, total = query_list_places(
                db=db,
                city_id=city_id or None,
                limit=page_size,
                offset=offset,
            )
    except Exception as exc:
        logger.exception(
            "places_query_failed city_id=%s lat=%s lng=%s error=%s",
            city_id, lat, lng, exc,
        )
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")

    # ── Layer 2+3: Ranking + Diversity (skipped on pages > 1) ────────────────
    if offset == 0 and candidates:
        ranked = rank_feed(
            candidates,
            lat=lat,
            lng=lng,
            limit=page_size,
        )
    else:
        ranked = candidates[:page_size]

    # ── Attach images and serialize ───────────────────────────────────────────
    place_ids = [p.id for p in ranked]
    image_urls = get_primary_image_urls_bulk(db, place_ids=place_ids)

    items = []
    for p in ranked:
        try:
            p.primary_image_url = image_urls.get(p.id)
            items.append(PlaceOut.model_validate(p, from_attributes=True))
        except Exception as exc:
            logger.debug(
                "places_serialize_failed place_id=%s error=%s",
                getattr(p, "id", None), exc,
            )

    response = PlacesResponse(total=total, page=page, page_size=page_size, items=items)

    logger.info(
        "API_RESPONSE endpoint=/places city_id=%s lat=%s lng=%s "
        "radius_miles=%s page=%s count=%s total=%s",
        city_id, lat, lng, radius_miles, page, len(items), total,
    )

    try:
        response_cache.set(cache_key, response, feed_ttl(city_id=city_id))
    except Exception as exc:
        logger.debug("places_cache_write_failed error=%s", exc)

    return response


@router.get("/{place_id}/menu", summary="Get menu items for a place")
def get_place_menu(
    place_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit),
) -> dict:
    place_id = (place_id or "").strip()
    if not place_id:
        raise HTTPException(status_code=400, detail="Invalid place_id")

    exists = db.execute(
        select(Place.id).where(Place.id == place_id, Place.is_active.is_(True))
    ).first()
    if not exists:
        raise HTTPException(status_code=404, detail="Place not found")

    rows = (
        db.query(MenuItem)
        .filter(MenuItem.place_id == place_id, MenuItem.is_active.is_(True))
        .order_by(MenuItem.category.asc(), MenuItem.name.asc())
        .limit(200)
        .all()
    )

    items = [
        {
            "id": row.id,
            "name": row.name,
            "price": row.price,
            "description": row.description,
            "category": row.category,
        }
        for row in rows
    ]

    return {"items": items}
