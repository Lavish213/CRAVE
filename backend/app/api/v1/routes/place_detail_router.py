from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.place import Place
from app.db.models.place_image import PlaceImage
from app.db.models.category import Category
from app.db.models.place_categories import place_categories

from app.services.cache.response_cache import response_cache
from app.services.cache.cache_keys import place_detail_key
from app.services.cache.cache_ttl import place_detail_ttl


router = APIRouter(
    prefix="/place",
    tags=["place"],
)


@router.get("/{place_id}")
def get_place_detail(
    *,
    place_id: str,
    db: Session = Depends(get_db),
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
        if not img.url or img.url in seen:
            continue
        seen.add(img.url)
        image_urls.append(img.url)

    # fallback (prevents empty UI cards)
    if not image_urls:
        image_urls = ["https://via.placeholder.com/800x600?text=No+Image"]

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
        .order_by(
            Category.name.asc(),
            Category.id.asc(),
        )
    )

    categories = db.execute(cat_stmt).scalars().all()

    seen_cat = set()
    category_names: List[str] = []

    for c in categories:
        if not c.name or c.name in seen_cat:
            continue
        seen_cat.add(c.name)
        category_names.append(c.name)

    # --------------------------------------------------
    # Response
    # --------------------------------------------------

    result = {
        "id": place.id,
        "name": place.name,
        "city_id": place.city_id,
        "lat": place.lat,
        "lng": place.lng,
        "price_tier": place.price_tier,
        "rank_score": float(place.rank_score or 0.0),
        "master_score": float(place.master_score or 0.0),
        "confidence_score": float(place.confidence_score or 0.0),
        "operational_confidence": float(place.operational_confidence or 0.0),
        "local_validation": float(place.local_validation or 0.0),
        "website": place.website or None,
        "grubhub_url": place.grubhub_url or None,
        "images": image_urls,
        "categories": category_names,
        "created_at": place.created_at,
        "updated_at": place.updated_at,
    }

    # --------------------------------------------------
    # Cache
    # --------------------------------------------------

    response_cache.set(
        cache_key,
        result,
        place_detail_ttl(place_id=place_id),
    )

    return result