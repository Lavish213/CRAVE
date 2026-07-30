from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_, select

from app.db.models.place import Place
from app.db.models.place_image import PlaceImage, VISIBILITY_HIDDEN
from app.db.models.place_categories import place_categories
from app.services.geo.bounding_box import bounding_box
from app.services.query.place_image_query import _to_proxy_url
from app.services.query.place_category_query import get_categories_for_places_bulk

logger = logging.getLogger(__name__)


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
    # Input Safety (prevents silent crashes)
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
    # Bounding Box (safe)
    # ---------------------------------------------------------

    try:
        bb = bounding_box(lat, lng, radius_km)
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
    # Primary Image Subquery
    # ---------------------------------------------------------

    primary_img_url = (
        select(PlaceImage.url)
        .where(
            and_(
                PlaceImage.place_id == Place.id,
                PlaceImage.is_primary.is_(True),
                PlaceImage.visibility_status != VISIBILITY_HIDDEN,
            )
        )
        .order_by(
            PlaceImage.confidence.desc(),
            PlaceImage.created_at.desc(),
            PlaceImage.id.asc(),
        )
        .limit(1)
        .scalar_subquery()
    )

    # ---------------------------------------------------------
    # Query (fully safe)
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
                Place.has_menu,
                primary_img_url.label("primary_image_url"),
            )
            .filter(
                Place.is_active.is_(True),

                # CRITICAL: prevent NULL comparison crashes
                Place.lat.isnot(None),
                Place.lng.isnot(None),

                Place.lat >= bb.min_lat,
                Place.lat <= bb.max_lat,
                Place.lng >= bb.min_lng,
                Place.lng <= bb.max_lng,
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
            # Place.id is already the primary key, so a plain .distinct()
            # (SQL "SELECT DISTINCT", not Postgres's column-specific
            # DISTINCT ON) is enough and doesn't restrict ORDER BY — using
            # .distinct(Place.id) here compiled to "DISTINCT ON (id) ...
            # ORDER BY rank_score DESC, id ASC", which Postgres rejects
            # outright ("SELECT DISTINCT ON expressions must match initial
            # ORDER BY expressions"), silently caught below on every call.
            q.distinct()
            .order_by(
                Place.rank_score.desc(),
                Place.id.asc(),
            )
            .limit(limit)
        )

        rows = list(q.all())

    except Exception as exc:
        # HARD FAIL SAFE → prevents API crash
        logger.exception(
            "map_query_failed lat=%s lng=%s city_id=%s category_id=%s error=%s",
            lat, lng, city_id, category_id, exc,
        )
        return {
            "ok": False,
            "center": {"lat": lat, "lng": lng},
            "radius_km": radius_km,
            "limit": limit,
            "count": 0,
            "places": [],
        }

    # ---------------------------------------------------------
    # Categories (bulk, single query — avoids N+1 per pin)
    # ---------------------------------------------------------

    try:
        category_map = get_categories_for_places_bulk(
            db, place_ids=[r.id for r in rows]
        )
    except Exception:
        category_map = {}

    # ---------------------------------------------------------
    # Mapping (safe casting)
    # ---------------------------------------------------------

    items: List[Dict[str, Any]] = []

    for r in rows:
        try:
            cats = category_map.get(r.id) or []
            category = getattr(cats[0], "name", None) if cats else None

            items.append(
                {
                    "id": r.id,
                    "name": r.name,
                    "lat": float(r.lat),
                    "lng": float(r.lng),
                    "city_id": r.city_id,
                    "price_tier": r.price_tier,
                    "rank_score": float(r.rank_score or 0.0),
                    "primary_image_url": _to_proxy_url(r.primary_image_url),
                    "category": category,
                    "has_menu": bool(r.has_menu),
                }
            )
        except Exception:
            continue  # skip bad rows safely

    return {
        "ok": True,
        "center": {"lat": lat, "lng": lng},
        "radius_km": radius_km,
        "limit": limit,
        "count": len(items),
        "places": items,
    }


get_map_places = fetch_places_for_map


# --- GeoJSON / Mapbox support ---

def _compute_tier_thresholds(scores: list) -> dict:
    """
    Compute percentile-based tier thresholds from the scores in this result set.
    elite = top 5%, trusted = next 15%, solid = next 30%, default = bottom 50%.
    """
    if not scores:
        return {"elite": float("inf"), "trusted": float("inf"), "solid": float("inf")}

    sorted_scores = sorted(scores)
    n = len(sorted_scores)

    elite_idx   = max(0, int(n * 0.95))
    trusted_idx = max(0, int(n * 0.80))
    solid_idx   = max(0, int(n * 0.50))

    return {
        "elite":   sorted_scores[elite_idx],
        "trusted": sorted_scores[trusted_idx],
        "solid":   sorted_scores[solid_idx],
    }


def _assign_tier(score: float, thresholds: dict) -> str:
    if score >= thresholds["elite"]:
        return "elite"
    if score >= thresholds["trusted"]:
        return "trusted"
    if score >= thresholds["solid"]:
        return "solid"
    return "default"


def fetch_places_for_map_geojson(
    db,
    *,
    lat: float,
    lng: float,
    radius_km: float = None,
    limit: int = None,
    city_id=None,
    category_id=None,
) -> dict:
    """
    Returns a Mapbox-compatible GeoJSON FeatureCollection dict.
    Wraps fetch_places_for_map — same query, same cache eligibility.
    Tiers are percentile-based within this result set.
    """
    # Build kwargs — only pass params that fetch_places_for_map accepts
    kwargs = {"db": db, "lat": lat, "lng": lng}
    if radius_km is not None:
        kwargs["radius_km"] = radius_km
    if limit is not None:
        kwargs["limit"] = limit
    if city_id is not None:
        kwargs["city_id"] = city_id
    if category_id is not None:
        kwargs["category_id"] = category_id

    result = fetch_places_for_map(**kwargs)
    places = result.get("places", [])
    scores = [p.get("rank_score", 0.0) for p in places]
    thresholds = _compute_tier_thresholds(scores)

    features = []
    for p in places:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [p.get("lng"), p.get("lat")],
            },
            "properties": {
                "id": p.get("id"),
                "name": p.get("name"),
                "city_id": p.get("city_id"),
                "tier": _assign_tier(p.get("rank_score", 0.0), thresholds),
                "rank_score": p.get("rank_score", 0.0),
                "price_tier": p.get("price_tier"),
                "primary_image_url": _to_proxy_url(p.get("primary_image_url")),
                "category": p.get("category"),
                "has_menu": bool(p.get("has_menu", False)),
            },
        })

    return {"type": "FeatureCollection", "features": features}
