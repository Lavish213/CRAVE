# FILE: backend/app/api/v1/routes/cities.py

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.query.cities_query import get_cities

from app.services.cache.response_cache import response_cache
from app.services.cache.cache_keys import cities_cache_key
from app.services.cache.cache_ttl import cities_ttl

from app.api.v1.schemas.cities import CityOut


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/cities",
    tags=["cities"],
)


@router.get(
    "",
    response_model=List[CityOut],
    summary="List active cities",
)
def get_cities_endpoint(
    *,
    db: Session = Depends(get_db),
) -> List[CityOut]:
    """
    Returns all active cities.

    Guarantees
    ----------
    • deterministic ordering
    • safe fallback (never crashes)
    • cache-backed response
    """

    cache_key = cities_cache_key()

    # -----------------------------
    # CACHE READ (SAFE)
    # -----------------------------
    try:
        cached = response_cache.get(cache_key)
        if cached is not None:
            return cached
    except Exception as exc:
        logger.debug("cities_cache_read_failed error=%s", exc)

    # -----------------------------
    # QUERY (SAFE)
    # -----------------------------
    try:
        cities = get_cities(db=db) or []
    except Exception as exc:
        logger.exception("cities_query_failed error=%s", exc)
        return []

    # -----------------------------
    # VALIDATION (SAFE)
    # -----------------------------
    result: List[CityOut] = []

    for c in cities:
        try:
            result.append(
                CityOut.model_validate(c, from_attributes=True)
            )
        except Exception as exc:
            logger.debug(
                "city_validation_failed error=%s raw=%s",
                exc,
                c,
            )

    # -----------------------------
    # CACHE WRITE (SAFE)
    # -----------------------------
    try:
        response_cache.set(
            cache_key,
            result,
            cities_ttl(),
        )
    except Exception as exc:
        logger.debug("cities_cache_write_failed error=%s", exc)

    return result