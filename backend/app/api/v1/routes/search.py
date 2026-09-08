# FILE: backend/app/api/v1/routes/search.py

from __future__ import annotations

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.search.search_engine import execute_search
from app.core.rate_limit import rate_limit

from app.services.cache.response_cache import response_cache
from app.services.cache.cache_keys import search_cache_key
from app.services.cache.cache_ttl import search_ttl

from app.api.v1.schemas.search import SearchInterpretationOut, SearchResponse
from app.api.v1.schemas.place_card import PlaceCardOut
from app.services.query.place_image_visibility_query import get_primary_image_urls_bulk
from app.services.query.place_video_visibility_query import get_has_video_bulk
from app.services.query.rank_percentile_query import get_rank_percentiles
from app.services.search.query_interpreter import interpret_search_query


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
    radius_miles: Optional[float] = Query(
        None, gt=0, le=100,
        description="Exclude results beyond this distance. Requires lat/lng; ignored otherwise.",
    ),
    page: int = Query(DEFAULT_PAGE, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit),
) -> SearchResponse:

    page = _clamp_page(page)
    page_size = _clamp_page_size(page_size)

    query = _clean_str(query)
    city_id = _clean_str(city_id)
    category_id = _clean_str(category_id)

    interpretation = interpret_search_query(query or "")
    interpretation_out = SearchInterpretationOut(
        original_query=interpretation.original_query,
        lookup_query=interpretation.lookup_query,
        price_tier=interpretation.price_tier,
        required_categories=list(interpretation.required_categories),
        hard_constraints=list(interpretation.hard_constraints),
        unsupported_hard_constraints=list(interpretation.unsupported_hard_constraints),
        context=list(interpretation.context),
        uncertain=interpretation.uncertain,
    )

    if not query or interpretation.unsupported_hard_constraints:
        return SearchResponse(
            total=0, page=page, page_size=page_size, items=[],
            interpretation=interpretation_out,
        )

    # A radius without a location to measure from is meaningless -- ignore
    # it rather than silently filtering against a nonexistent point.
    effective_radius_miles = radius_miles if (lat is not None and lng is not None) else None

    cache_key = search_cache_key(
        query=query,
        city_id=city_id,
        category_id=category_id,
        price_tier=price_tier,
        lat=lat,
        lng=lng,
        radius_miles=effective_radius_miles,
        page=page,
        page_size=page_size,
    )

    try:
        cached = response_cache.get(cache_key)
        if cached is not None:
            return cached
    except Exception as exc:
        logger.debug("search_cache_read_failed error=%s", exc)

    offset = (page - 1) * page_size

    try:
        results, total = execute_search(
            db,
            query=interpretation.lookup_query,
            city_id=city_id,
            category_id=category_id,
            price_tier=price_tier if price_tier is not None else interpretation.price_tier,
            lat=lat,
            lng=lng,
            radius_miles=effective_radius_miles,
            limit=page_size,
            offset=offset,
            required_category_names=interpretation.required_categories,
        )
    except Exception as exc:
        logger.exception(
            "search_query_failed query=%s city_id=%s error=%s",
            query,
            city_id,
            exc,
        )
        raise HTTPException(status_code=503, detail="Search temporarily unavailable") from exc

    relaxed_constraints: List[str] = []
    # Radius is a soft (user-adjustable) preference, same standing as
    # price below -- relax it only when the filtered query has no matches
    # at all, never touching an actual hard constraint (dietary/allergy).
    if total == 0 and effective_radius_miles is not None:
        try:
            results, total = execute_search(
                db,
                query=interpretation.lookup_query,
                city_id=city_id,
                category_id=category_id,
                price_tier=price_tier if price_tier is not None else interpretation.price_tier,
                lat=lat,
                lng=lng,
                radius_miles=None,
                limit=page_size,
                offset=offset,
                required_category_names=interpretation.required_categories,
            )
        except Exception as exc:
            logger.exception("search_relaxation_failed query=%s error=%s", query, exc)
            raise HTTPException(status_code=503, detail="Search temporarily unavailable") from exc
        relaxed_constraints.append("radius")

    # Price is a soft heuristic. Relax it only when the filtered query has
    # no matches at all. An empty later page with total > 0 is pagination,
    # not evidence that the price constraint should be changed.
    if total == 0 and interpretation.price_tier is not None and price_tier is None:
        try:
            results, total = execute_search(
                db,
                query=interpretation.lookup_query,
                city_id=city_id,
                category_id=category_id,
                price_tier=price_tier,
                lat=lat,
                lng=lng,
                radius_miles=None,
                limit=page_size,
                offset=offset,
                required_category_names=interpretation.required_categories,
            )
        except Exception as exc:
            logger.exception("search_relaxation_failed query=%s error=%s", query, exc)
            raise HTTPException(status_code=503, detail="Search temporarily unavailable") from exc
        relaxed_constraints.append("price")
        if effective_radius_miles is not None:
            relaxed_constraints.append("radius")

    place_ids = [getattr(p, "id", None) for p in results if getattr(p, "id", None)]
    image_urls = get_primary_image_urls_bulk(db, place_ids=place_ids)
    video_flags = get_has_video_bulk(db, place_ids=place_ids)
    rank_percentiles = get_rank_percentiles(db, place_ids=place_ids)

    items: List[PlaceCardOut] = []

    for p in results:
        try:
            pid = getattr(p, "id", None)
            img = image_urls.get(pid)
            p.primary_image_url = img
            p.primary_image = img
            p.has_video = video_flags.get(pid, False)
            p.rank_percentile = rank_percentiles.get(pid)
            items.append(PlaceCardOut.model_validate(p, from_attributes=True))
        except Exception:
            logger.exception(
                "search_serialize_failed place_id=%s",
                getattr(p, "id", None),
            )

    # Retrieval may strip supported intent words from lookup_query. Exact-name
    # navigation must compare against what the user actually typed so a place
    # such as "Vegan Ramen House" can still be recognized exactly.
    normalized_original_query = interpretation.original_query.strip().casefold()
    exact_match_id = next(
        (
            item.id for item in items
            if item.name.strip().casefold() == normalized_original_query
        ),
        None,
    )

    response = SearchResponse(
        total=int(total or 0),
        page=page,
        page_size=page_size,
        items=items,
        interpretation=interpretation_out,
        exact_match_id=exact_match_id,
        relaxed_constraints=relaxed_constraints,
    )

    logger.info(
        "API_RESPONSE endpoint=/search query_len=%s city_id=%s count=%s total=%s",
        len(query) if query else 0, city_id, len(items), total,
    )

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
