from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.query.places_query import list_places as query_list_places
from app.services.feed.feed_bucket_manager import get_feed_places
from app.services.query.place_image_query import get_primary_image_urls_bulk
from app.api.v1.schemas.places import PlacesResponse, PlaceOut

from app.services.cache.response_cache import response_cache
from app.services.cache.cache_keys import feed_key
from app.services.cache.cache_ttl import feed_ttl
from app.core.rate_limit import rate_limit


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/places",
    tags=["places"],
)


@router.get(
    "",
    response_model=PlacesResponse,
    summary="List ranked places",
)
def get_places(
    city_id: str = Query(..., description="City UUID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit),
) -> PlacesResponse:

    cache_key = feed_key(
        city_id=city_id,
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

    try:
        if page == 1 and city_id:
            try:
                results, total = get_feed_places(
                    db=db,
                    city_id=city_id,
                    limit=page_size,
                )
            except Exception as feed_exc:
                logger.warning(
                    "feed_mixer_failed city_id=%s error=%s — falling back to rank query",
                    city_id,
                    feed_exc,
                )
                results, total = query_list_places(
                    db=db,
                    city_id=city_id,
                    limit=page_size,
                    offset=offset,
                )
        else:
            results, total = query_list_places(
                db=db,
                city_id=city_id,
                limit=page_size,
                offset=offset,
            )
    except Exception as exc:
        logger.exception("places_query_failed city_id=%s error=%s", city_id, exc)
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")

    # Bulk image lookup — one query for the entire page
    place_ids = [p.id for p in results]
    image_urls = get_primary_image_urls_bulk(db, place_ids=place_ids)

    items = []
    for p in results:
        try:
            p.primary_image_url = image_urls.get(p.id)
            items.append(PlaceOut.model_validate(p, from_attributes=True))
        except Exception as exc:
            logger.debug(
                "places_serialize_failed place_id=%s error=%s",
                getattr(p, "id", None),
                exc,
            )

    response = PlacesResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )

    try:
        response_cache.set(cache_key, response, feed_ttl(city_id=city_id))
    except Exception as exc:
        logger.debug("places_cache_write_failed error=%s", exc)

    return response
