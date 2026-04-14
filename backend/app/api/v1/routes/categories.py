from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.query.category_query import list_categories
from app.api.v1.schemas.categories import CategoriesResponse, CategoryOut

from app.services.cache.response_cache import response_cache
from app.services.cache.cache_keys import categories_cache_key
from app.services.cache.cache_ttl import categories_ttl


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/categories",
    tags=["categories"],
)


@router.get(
    "",
    response_model=CategoriesResponse,
    summary="List categories",
)
def get_categories(
    db: Session = Depends(get_db),
) -> CategoriesResponse:
    """
    Returns all active categories.

    Guarantees
    ----------
    • deterministic ordering
    • read-only endpoint
    • cache-backed response
    """

    cache_key = categories_cache_key()

    # -----------------------------
    # CACHE READ (SAFE)
    # -----------------------------
    try:
        cached = response_cache.get(cache_key)
        if cached is not None:
            return cached
    except Exception as exc:
        logger.debug("categories_cache_read_failed error=%s", exc)

    # -----------------------------
    # QUERY (SAFE)
    # -----------------------------
    try:
        categories = list_categories(db) or []
    except Exception as exc:
        logger.exception("categories_query_failed error=%s", exc)
        return CategoriesResponse(total=0, items=[])

    # -----------------------------
    # VALIDATION (SAFE)
    # -----------------------------
    items: list[CategoryOut] = []

    for c in categories:
        try:
            items.append(
                CategoryOut.model_validate(c, from_attributes=True)
            )
        except Exception as exc:
            logger.debug(
                "category_validation_failed error=%s raw=%s",
                exc,
                c,
            )

    result = CategoriesResponse(
        total=len(items),
        items=items,
    )

    # -----------------------------
    # CACHE WRITE (SAFE)
    # -----------------------------
    try:
        response_cache.set(
            cache_key,
            result,
            categories_ttl(),
        )
    except Exception as exc:
        logger.debug("categories_cache_write_failed error=%s", exc)

    return result
