from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.query.places_query import list_places as query_list_places
from app.api.v1.schemas.places import PlacesResponse, PlaceOut

from app.services.cache.response_cache import response_cache
from app.services.cache.cache_keys import feed_key
from app.services.cache.cache_ttl import feed_ttl


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
) -> PlacesResponse:

    cache_key = feed_key(
        city_id=city_id,
        page=page,
        page_size=page_size,
    )

    cached = response_cache.get(cache_key)
    if cached is not None:
        return cached

    offset = (page - 1) * page_size

    results, total = query_list_places(
        db=db,
        city_id=city_id,
        limit=page_size,
        offset=offset,
    )

    response = PlacesResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[
            PlaceOut.model_validate(p, from_attributes=True)
            for p in results
        ],
    )

    response_cache.set(
        cache_key,
        response,
        feed_ttl(city_id=city_id),
    )

    return response