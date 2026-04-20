from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.db.models.place_categories import place_categories
from app.db.models.place_image import PlaceImage

DEFAULT_LIMIT = 250
MAX_LIMIT = 1000


def _clamp_limit(limit: int) -> int:
    try:
        n = int(limit)
    except Exception:
        return DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, n))


def _compute_tier_thresholds(scores: List[float]) -> Dict[str, float]:
    if not scores:
        return {
            "elite": float("inf"),
            "trusted": float("inf"),
            "solid": float("inf"),
        }

    sorted_scores = sorted(scores)
    n = len(sorted_scores)

    elite_idx = max(0, min(n - 1, int(n * 0.95)))
    trusted_idx = max(0, min(n - 1, int(n * 0.80)))
    solid_idx = max(0, min(n - 1, int(n * 0.50)))

    return {
        "elite": sorted_scores[elite_idx],
        "trusted": sorted_scores[trusted_idx],
        "solid": sorted_scores[solid_idx],
    }


def _assign_tier(score: float, thresholds: Dict[str, float]) -> str:
    if score >= thresholds["elite"]:
        return "elite"
    if score >= thresholds["trusted"]:
        return "trusted"
    if score >= thresholds["solid"]:
        return "solid"
    return "default"


def fetch_places_for_map(
    db: Session,
    *,
    lat: float,
    lng: float,
    radius_km: float = 10.0,
    limit: int = DEFAULT_LIMIT,
    city_id: Optional[str] = None,
    category_id: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        lat = float(lat)
        lng = float(lng)
    except Exception:
        return {
            "ok": False,
            "center": {"lat": 0.0, "lng": 0.0},
            "radius_km": radius_km,
            "limit": limit,
            "count": 0,
            "places": [],
        }

    limit = _clamp_limit(limit)

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

        rows = (
            q.distinct(Place.id)
            .order_by(
                Place.rank_score.desc(),
                Place.id.asc(),
            )
            .limit(limit)
            .all()
        )
    except Exception:
        return {
            "ok": False,
            "center": {"lat": lat, "lng": lng},
            "radius_km": radius_km,
            "limit": limit,
            "count": 0,
            "places": [],
        }

    items: List[Dict[str, Any]] = []

    for r in rows:
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


def fetch_places_for_map_geojson(
    db: Session,
    *,
    lat: float,
    lng: float,
    radius_km: Optional[float] = None,
    limit: Optional[int] = None,
    city_id: Optional[str] = None,
    category_id: Optional[str] = None,
) -> Dict[str, Any]:
    result = fetch_places_for_map(
        db=db,
        lat=lat,
        lng=lng,
        radius_km=radius_km or 10.0,
        limit=limit or DEFAULT_LIMIT,
        city_id=city_id,
        category_id=category_id,
    )

    places = result.get("places", [])
    scores = [float(p.get("rank_score") or 0.0) for p in places]
    thresholds = _compute_tier_thresholds(scores)

    features: List[Dict[str, Any]] = []

    for p in places:
        try:
            lat_v = float(p["lat"])
            lng_v = float(p["lng"])
        except Exception:
            continue

        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lng_v, lat_v],
                },
                "properties": {
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "city_id": p.get("city_id"),
                    "tier": _assign_tier(float(p.get("rank_score") or 0.0), thresholds),
                    "rank_score": float(p.get("rank_score") or 0.0),
                    "price_tier": p.get("price_tier"),
                    "primary_image_url": p.get("primary_image_url"),
                    "has_menu": False,
                },
            }
        )

    return {
        "type": "FeatureCollection",
        "features": features,
    }


get_map_places = fetch_places_for_map
get_map_places_geojson = fetch_places_for_map_geojson