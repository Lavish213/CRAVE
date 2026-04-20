from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_, select

from app.db.models.place import Place
from app.db.models.place_image import PlaceImage
from app.db.models.place_categories import place_categories


DEFAULT_RADIUS_KM = 5.0
DEFAULT_LIMIT = 250
MAX_LIMIT = 1000


def _clamp_limit(limit: int) -> int:
    try:
        n = int(limit)
    except Exception:
        return DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, n))


def fetch_places_for_map(
    db: Session,
    *,
    lat: float,
    lng: float,
    radius_km: float = DEFAULT_RADIUS_KM,
    limit: int = DEFAULT_LIMIT,
    city_id: Optional[str] = None,
    category_id: Optional[str] = None,
) -> Dict[str, Any]:

    # ---------------------------------------------------------
    # Input Safety
    # ---------------------------------------------------------

    try:
        lat = float(lat)
        lng = float(lng)
        radius_km = float(radius_km)
    except Exception:
        return {
            "ok": False,
            "center": {"lat": lat, "lng": lng},
            "radius_km": radius_km,
            "limit": limit,
            "count": 0,
            "places": [],
        }

    limit = _clamp_limit(limit)

    # ---------------------------------------------------------
    # Primary Image Subquery
    # ---------------------------------------------------------

    primary_img_url = (
        select(PlaceImage.url)
        .where(
            and_(
                PlaceImage.place_id == Place.id,
                PlaceImage.is_primary.is_(True),
            )
        )
        .order_by(
            PlaceImage.created_at.desc(),
            PlaceImage.id.asc(),
        )
        .limit(1)
        .scalar_subquery()
    )

    # ---------------------------------------------------------
    # CORE QUERY
    # ---------------------------------------------------------

    try:
        q = (
            db.query(
                Place.id,
                Place.name,
                Place.lat,
                Place.lng,
                Place.city_id,
                Place.price_tier,
                Place.rank_score,
                primary_img_url.label("primary_image_url"),
            )
            .filter(
                Place.is_active.is_(True),
                Place.lat.isnot(None),
                Place.lng.isnot(None),
            )
        )

        if city_id:
            q = q.filter(Place.city_id == city_id)

        if category_id:
            q = (
                q.join(
                    place_categories,
                    place_categories.c.place_id == Place.id,
                )
                .filter(place_categories.c.category_id == category_id)
            )

        q = (
            q.distinct(Place.id)
            .order_by(
                Place.rank_score.desc(),
                Place.id.asc(),
            )
            .limit(limit)
        )

        rows = list(q.all())

    except Exception:
        return {
            "ok": False,
            "center": {"lat": lat, "lng": lng},
            "radius_km": radius_km,
            "limit": limit,
            "count": 0,
            "places": [],
        }

    # ---------------------------------------------------------
    # FALLBACK (ONLY IF EMPTY)
    # ---------------------------------------------------------

    if not rows:
        try:
            from app.services.feed.feed_builder import build_feed

            feed = build_feed(
                db=db,
                lat=lat,
                lng=lng,
                radius_km=radius_km,
                limit=limit,
            )

            feed_places = feed.get("places", [])

            items = []
            for p in feed_places:
                if p.get("lat") is None or p.get("lng") is None:
                    continue

                try:
                    items.append(
                        {
                            "id": p.get("id"),
                            "name": p.get("name"),
                            "lat": float(p.get("lat")),
                            "lng": float(p.get("lng")),
                            "city_id": p.get("city_id"),
                            "price_tier": p.get("price_tier"),
                            "rank_score": float(p.get("rank_score") or 0),
                            "primary_image_url": p.get("primary_image_url"),
                        }
                    )
                except Exception:
                    continue

            return {
                "ok": True,
                "center": {"lat": lat, "lng": lng},
                "radius_km": radius_km,
                "limit": limit,
                "count": len(items),
                "places": items,
            }

        except Exception:
            pass

    # ---------------------------------------------------------
    # Mapping
    # ---------------------------------------------------------

    items: List[Dict[str, Any]] = []

    for r in rows:
        if r.lat is None or r.lng is None:
            continue

        try:
            items.append(
                {
                    "id": r.id,
                    "name": r.name,
                    "lat": float(r.lat),
                    "lng": float(r.lng),
                    "city_id": r.city_id,
                    "price_tier": r.price_tier,
                    "rank_score": float(r.rank_score or 0.0),
                    "primary_image_url": r.primary_image_url,
                }
            )
        except Exception:
            continue

    return {
        "ok": True,
        "center": {"lat": lat, "lng": lng},
        "radius_km": radius_km,
        "limit": limit,
        "count": len(items),
        "places": items,
    }


get_map_places = fetch_places_for_map