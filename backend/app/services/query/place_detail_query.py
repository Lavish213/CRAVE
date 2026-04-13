from __future__ import annotations

from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.models.place import Place
from app.db.models.place_image import PlaceImage
from app.db.models.category import Category
from app.db.models.place_categories import place_categories


def get_place_detail(
    db: Session,
    *,
    place_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Production-safe place detail query.

    Guarantees
    ----------
    • active places only
    • deterministic ordering
    • join-table safe category loading
    • no ranking logic
    • SQLite/Postgres safe
    """

    place_id = (place_id or "").strip()
    if not place_id:
        return None

    # --------------------------------------------------
    # Fetch place
    # --------------------------------------------------

    stmt = (
        select(Place)
        .where(
            Place.id == place_id,
            Place.is_active.is_(True),
        )
        .limit(1)
    )

    place = db.execute(stmt).scalar_one_or_none()

    if not place:
        return None

    # --------------------------------------------------
    # Fetch images
    # --------------------------------------------------

    img_stmt = (
        select(PlaceImage.url)
        .where(
            PlaceImage.place_id == place_id,
        )
        .order_by(
            PlaceImage.created_at.desc(),
            PlaceImage.id.asc(),
        )
    )

    image_rows = db.execute(img_stmt).scalars().all()

    images: List[str] = [url for url in image_rows if url]

    # --------------------------------------------------
    # Fetch categories
    # --------------------------------------------------

    cat_stmt = (
        select(Category.name)
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

    category_rows = db.execute(cat_stmt).scalars().all()

    categories: List[str] = [name for name in category_rows if name]

    # --------------------------------------------------
    # Primary image
    # --------------------------------------------------

    primary_image_url: Optional[str] = images[0] if images else None

    # --------------------------------------------------
    # Response
    # --------------------------------------------------

    return {
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
        "primary_image_url": primary_image_url,
        "images": images,
        "categories": categories,
        "created_at": place.created_at,
        "updated_at": place.updated_at,
    }