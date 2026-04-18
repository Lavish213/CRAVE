# FILE: backend/app/api/v1/routes/search.py

from __future__ import annotations

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.search.search_engine import execute_search
from app.core.rate_limit import rate_limit

from app.services.cache.response_cache import response_cache
from app.services.cache.cache_keys import search_cache_key
from app.services.cache.cache_ttl import search_ttl

from app.api.v1.schemas.search import SearchResponse
from app.api.v1.schemas.place_card import PlaceCardOut
from app.services.query.place_image_query import get_primary_image_urls_bulk


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/search",
    tags=["search"],
)


DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _clamp_page(page: int) -> int:
    try:
        p = int(page)
    except Exception:
        return DEFAULT_PAGE
    return max(1, p)


def _clamp_page_size(size: int) -> int:
    try:
        s = int(size)
    except Exception:
        return DEFAULT_PAGE_SIZE
    return max(1, min(MAX_PAGE_SIZE, s))


def _clean_str(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        v = str(value).strip()
        return v or None
    except Exception:
        return None


@router.get(
    "",
    response_model=SearchResponse,
    summary="Search places",
)
def search(
    query: str = Query(..., min_length=1),
    city_id: Optional[str] = Query(None, description="Optional city scope — omit for global search"),
    category_id: Optional[str] = Query(None),
    price_tier: Optional[int] = Query(None, ge=1, le=4),
    lat: Optional[float] = Query(None, description="User latitude for proximity ranking"),
    lng: Optional[float] = Query(None, description="User longitude for proximity ranking"),
    page: int = Query(DEFAULT_PAGE, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit),
) -> SearchResponse:

    # -----------------------------
    # Normalize inputs
    # -----------------------------
    page = _clamp_page(page)
    page_size = _clamp_page_size(page_size)

    query = _clean_str(query)
    city_id = _clean_str(city_id)  # may be None → global search
    category_id = _clean_str(category_id)

    if not query:
        return SearchResponse(total=0, page=page, page_size=page_size, items=[])

    # -----------------------------
    # Cache read (safe)
    # -----------------------------
    cache_key = search_cache_key(
        query=query,
        city_id=city_id,
        category_id=category_id,
        price_tier=price_tier,
        page=page,
        page_size=page_size,
    )

    try:
        cached = response_cache.get(cache_key)
        if cached is not None:
            return cached
    except Exception as exc:
        logger.debug("search_cache_read_failed error=%s", exc)

    # -----------------------------
    # Query
    # -----------------------------
    offset = (page - 1) * page_size

    try:
        results, total = execute_search(
            db,
            query=query,
            city_id=city_id,
            category_id=category_id,
            price_tier=price_tier,
            lat=lat,
            lng=lng,
            limit=page_size,
            offset=offset,
        )
    except Exception as exc:
        logger.exception(
            "search_query_failed query=%s city_id=%s error=%s",
            query,
            city_id,
            exc,
        )
        return SearchResponse(
            total=0,
            page=page,
            page_size=page_size,
            items=[],
        )

    # -----------------------------
    # Serialize (safe)
    # -----------------------------
    # Bulk image lookup — one query for the entire result set
    place_ids = [getattr(p, "id", None) for p in results if getattr(p, "id", None)]
    image_urls = get_primary_image_urls_bulk(db, place_ids=place_ids)

    items: List[PlaceCardOut] = []

    for p in results:
        try:
            img = image_urls.get(getattr(p, "id", None))
            p.primary_image_url = img
            p.primary_image = img
            items.append(
                PlaceCardOut.model_validate(p, from_attributes=True)
            )
        except Exception as exc:
            logger.debug(
                "search_serialize_failed place_id=%s error=%s",
                getattr(p, "id", None),
                exc,
            )

    response = SearchResponse(
        total=int(total or 0),
        page=page,
        page_size=page_size,
        items=items,
    )

    logger.info(
        "API_RESPONSE endpoint=/search query_len=%s city_id=%s count=%s total=%s",
        len(query) if query else 0, city_id, len(items), total,
    )

    # -----------------------------
    # Cache write (safe)
    # -----------------------------
    try:
        response_cache.set(
            cache_key,
            response,
            search_ttl(query=query),
        )
    except Exception as exc:
        logger.debug(
            "search_cache_write_failed key=%s error=%s",
            cache_key,
            exc,
        )

    return response