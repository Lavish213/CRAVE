from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.db.session import get_db
from app.core.rate_limit import rate_limit
from app.db.models.place import Place
from app.db.models.place_image import PlaceImage
from app.db.models.category import Category
from app.db.models.place_categories import place_categories

from app.services.cache.response_cache import response_cache
from app.services.cache.cache_keys import place_detail_key
from app.services.cache.cache_ttl import place_detail_ttl
from app.services.query.place_image_query import _to_proxy_url


router = APIRouter(
    prefix="/place",
    tags=["place"],
)


@router.get("/{place_id}")
def get_place_detail(
    *,
    request: Request,
    place_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit),
) -> dict:

    place_id = (place_id or "").strip()
    if not place_id:
        raise HTTPException(status_code=400, detail="Invalid place_id")

    cache_key = place_detail_key(place_id=place_id)

    cached = response_cache.get(cache_key)
    if cached is not None:
        return cached

    # --------------------------------------------------
    # Fetch place
    # --------------------------------------------------

    stmt = select(Place).where(
        Place.id == place_id,
        Place.is_active.is_(True),
    )

    place = db.execute(stmt).scalar_one_or_none()

    if not place:
        raise HTTPException(
            status_code=404,
            detail="Place not found",
        )

    # --------------------------------------------------
    # Images (dedup + safe)
    # --------------------------------------------------

    img_stmt = (
        select(PlaceImage)
        .where(PlaceImage.place_id == place_id)
        .order_by(
            PlaceImage.is_primary.desc(),  # 🔥 primary first
            PlaceImage.created_at.desc(),
            PlaceImage.id.asc(),
        )
    )

    images = db.execute(img_stmt).scalars().all()

    seen = set()
    image_urls: List[str] = []

    for img in images:
        raw = img.url
        if not raw or raw in seen:
            continue
        seen.add(raw)
        proxied = _to_proxy_url(raw)
        if proxied:
            image_urls.append(proxied)

    # No image = null; UI handles gracefully

    # --------------------------------------------------
    # Categories (stable + dedup)
    # --------------------------------------------------

    cat_stmt = (
        select(Category)
        .join(
            place_categories,
            place_categories.c.category_id == Category.id,
        )
        .where(place_categories.c.place_id == place_id)
        .order_by(Category.name.asc(), Category.id.asc())
    )

    categories = db.execute(cat_stmt).scalars().all()

    _GENERIC = {"restaurant", "restaurants", "bar", "bars", "other", "others"}
    seen_cat: set = set()
    specific_names: List[str] = []
    generic_names: List[str] = []

    for c in categories:
        name = (c.name or "").strip()
        if not name or name in seen_cat:
            continue
        seen_cat.add(name)
        if name.lower() in _GENERIC:
            generic_names.append(name)
        else:
            specific_names.append(name)

    # Specific categories first; fall back to generic if nothing specific
    category_names = specific_names or generic_names

    # --------------------------------------------------
    # Response
    # --------------------------------------------------

    result = {
        "id": place.id,
        "name": place.name,
        "city_id": place.city_id,
        "address": place.address or None,
        "lat": place.lat,
        "lng": place.lng,
        "price_tier": place.price_tier,
        "has_menu": bool(place.has_menu),
        "rank_score": float(place.rank_score or 0.0),
        "master_score": float(place.master_score or 0.0),
        "confidence_score": float(place.confidence_score or 0.0),
        "operational_confidence": float(place.operational_confidence or 0.0),
        "local_validation": float(place.local_validation or 0.0),
        "website": place.website or None,
        "grubhub_url": place.grubhub_url or None,
        "images": image_urls,
        "primary_image_url": image_urls[0] if image_urls else None,
        # category: first category name for display; full list in categories
        "category": category_names[0] if category_names else None,
        "categories": category_names,
        "created_at": place.created_at,
        "updated_at": place.updated_at,
    }

    logger.info(
        "API_RESPONSE endpoint=/place/%s name=%s categories=%s images=%s lat=%s lng=%s",
        place_id, place.name, category_names, len(image_urls), place.lat, place.lng,
    )

    # --------------------------------------------------
    # Cache
    # --------------------------------------------------

    response_cache.set(
        cache_key,
        result,
        place_detail_ttl(place_id=place_id),
    )

    return result