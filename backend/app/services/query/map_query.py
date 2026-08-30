from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.db.models.place_categories import place_categories
from app.services.geo.bounding_box import bounding_box
from app.services.query.place_image_visibility_query import get_primary_image_urls_bulk
from app.services.query.place_category_query import get_categories_for_places_bulk
from app.services.query.rank_percentile_query import get_rank_percentiles

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
    except Exception as exc:
        raise ValueError("invalid map coordinates or radius") from exc

    limit = _clamp_limit(limit)

    # ---------------------------------------------------------
    # Bounding Box (safe)
    # ---------------------------------------------------------

    try:
        bb = bounding_box(lat, lng, radius_km)
    except Exception as exc:
        raise ValueError("invalid map bounding box") from exc

    # ---------------------------------------------------------
    # Query (fully safe)
    # ---------------------------------------------------------
    #
    # Primary image used to be resolved via a correlated scalar subquery
    # embedded per-row in this SELECT (one extra filtered-sort lookup
    # against place_images for every one of up to `limit` rows). Every
    # other list surface in the app (feed, search) resolves it as a
    # single separate bulk query instead (place_id IN (...), grouped in
    # Python — see get_primary_image_urls_bulk) specifically to avoid
    # that N+1-shaped cost. This was the one surface that never got that
    # treatment, and it's a real, live-confirmed cost: a production map
    # request timed out client-side at 25s while feed/search/detail all
    # loaded normally in the same session. Moved to the same bulk lookup
    # below, after the place rows are fetched.

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

    except Exception:
        logger.exception(
            "map_query_failed lat=%s lng=%s city_id=%s category_id=%s",
            lat, lng, city_id, category_id,
        )
        # An outage is not an empty catalog. Let the route translate this
        # into a retryable 503 so the client can preserve stale pins and tell
        # the user what actually happened.
        raise

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
    # Primary images (bulk, single query — same reasoning as categories
    # above; see the module-level comment on why this replaced a
    # per-row correlated subquery)
    # ---------------------------------------------------------

    try:
        image_map = get_primary_image_urls_bulk(
            db, place_ids=[r.id for r in rows]
        )
    except Exception:
        image_map = {}

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
                    "primary_image_url": image_map.get(r.id),
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

def _assign_tier(score: float, rank_percentile: Optional[float]) -> str:
    """Return a viewport-stable tier.

    A map pan must not change a place from Hidden Gem to CRAVE Pick merely
    because a different set of neighbors entered the response. Prefer the
    hourly per-city ranking snapshot used by Feed/Search. New places that are
    not in the snapshot yet use the same absolute-score fallback as the rest
    of the app.
    """
    if rank_percentile is not None:
        if rank_percentile >= 0.95:
            return "elite"
        if rank_percentile >= 0.80:
            return "trusted"
        if rank_percentile >= 0.40:
            return "solid"
        return "default"

    if score >= 0.42:
        return "elite"
    if score >= 0.32:
        return "trusted"
    if score >= 0.22:
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
    Tiers use the stable per-city percentile snapshot, matching Feed/Search.
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
    if not result.get("ok"):
        raise RuntimeError("map query failed")
    places = result.get("places", [])
    place_ids = [p.get("id") for p in places if p.get("id")]
    try:
        rank_percentiles = get_rank_percentiles(db, place_ids=place_ids)
    except Exception:
        logger.exception("map_rank_percentiles_failed place_count=%s", len(place_ids))
        rank_percentiles = {}

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
                "tier": _assign_tier(
                    p.get("rank_score", 0.0), rank_percentiles.get(p.get("id"))
                ),
                "rank_score": p.get("rank_score", 0.0),
                "price_tier": p.get("price_tier"),
                # Already proxy-formatted by get_primary_image_urls_bulk
                # (via fetch_places_for_map) — no second conversion needed.
                "primary_image_url": p.get("primary_image_url"),
                "category": p.get("category"),
                "has_menu": bool(p.get("has_menu", False)),
            },
        })

    return {"type": "FeatureCollection", "features": features}
