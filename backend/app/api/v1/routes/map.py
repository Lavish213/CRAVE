from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.query.map_query import fetch_places_for_map
from app.services.cache.response_cache import response_cache
from app.services.cache.cache_keys import map_key
from app.services.cache.cache_ttl import map_ttl
from app.api.v1.schemas.map import MapResponse, MapCenter


logger = logging.getLogger(__name__)


def _empty_map_response(lat: float, lng: float, radius_km: float, limit: int) -> MapResponse:
    """Build a valid empty MapResponse for error/fallback cases."""
    return MapResponse(
        ok=False,
        center=MapCenter(lat=lat, lng=lng),
        radius_km=radius_km,
        limit=limit,
        count=0,
        places=[],
    )


router = APIRouter(
    prefix="/map",
    tags=["map"],
)


DEFAULT_RADIUS_KM = 5.0
DEFAULT_LIMIT = 250
MAX_LIMIT = 1000


def _clamp_limit(limit: int) -> int:
    try:
        n = int(limit)
    except Exception:
        return DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, n))


def _safe_float(value: float) -> Optional[float]:
    try:
        v = float(value)
        return v
    except Exception:
        return None


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
    response_model=MapResponse,
    summary="Get places for map view",
)
def map_places(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    radius_km: float = Query(DEFAULT_RADIUS_KM, ge=0.1, le=50.0),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    city_id: Optional[str] = Query(None),
    category_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> MapResponse:

    lat = _safe_float(lat)
    lng = _safe_float(lng)

    if lat is None or lng is None:
        return _empty_map_response(0.0, 0.0, radius_km, limit)

    limit = _clamp_limit(limit)
    city_id = _clean_str(city_id)
    category_id = _clean_str(category_id)

    # ---------------------------------------------------
    # Cache
    # ---------------------------------------------------

    cache_key = map_key(
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        limit=limit,
        city_id=city_id,
        category_id=category_id,
    )

    cached = response_cache.get(cache_key)
    if cached is not None:
        try:
            return MapResponse.model_validate(cached)
        except Exception:
            pass

    # ---------------------------------------------------
    # Query
    # ---------------------------------------------------

    try:
        result = fetch_places_for_map(
            db=db,
            lat=lat,
            lng=lng,
            radius_km=radius_km,
            limit=limit,
            city_id=city_id,
            category_id=category_id,
        )
    except Exception as exc:
        logger.error(
            "map_query_failed lat=%s lng=%s error=%s",
            lat,
            lng,
            exc,
        )
        return _empty_map_response(lat, lng, radius_km, limit)

    try:
        payload = MapResponse.model_validate(result)
    except Exception as exc:
        logger.error(
            "map_serialize_failed error=%s",
            exc,
        )
        return _empty_map_response(lat, lng, radius_km, limit)

    # ---------------------------------------------------
    # Cache set
    # ---------------------------------------------------

    try:
        response_cache.set(
            cache_key,
            payload.model_dump(),
            map_ttl(radius_km=radius_km),
        )
    except Exception as exc:
        logger.debug(
            "map_cache_failed key=%s error=%s",
            cache_key,
            exc,
        )

    return payload