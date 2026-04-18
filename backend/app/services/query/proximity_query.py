"""
proximity_query.py — Radius-based Candidate Retrieval

Retrieves Place candidates within a radius of (lat, lng) using a
bounding-box SQL pre-filter + Pythagorean dist² ordering.

This is Layer 1 (retrieval) only.
All ranking decisions belong in feed_ranker.rank_feed().
"""
from __future__ import annotations

import math
from typing import List, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models.place import Place

_DEG_KM = 111.0   # 1 degree ≈ 111 km
_MILES_TO_KM = 1.60934


def _bounding_box(lat: float, lng: float, radius_km: float):
    """Axis-aligned bounding box for the given radius."""
    delta_lat = radius_km / _DEG_KM
    lat_rad = math.radians(lat)
    delta_lng = radius_km / (_DEG_KM * max(math.cos(lat_rad), 0.01))
    return (
        lat - delta_lat, lat + delta_lat,
        lng - delta_lng, lng + delta_lng,
    )


def list_places_near(
    db: Session,
    *,
    lat: float,
    lng: float,
    radius_miles: float = 20.0,
    limit: int = 40,
    offset: int = 0,
) -> Tuple[List[Place], int]:
    """
    Return a candidate pool of active places within radius_miles of (lat, lng).

    Returns raw candidates ordered by dist² ASC, rank_score DESC.
    Callers must pass results through feed_ranker.rank_feed() for final ordering
    and diversity.

    Fetches limit*4 (capped at 400) candidates so rank_feed has enough
    material to produce a diverse, well-ranked page.
    """
    radius_km = radius_miles * _MILES_TO_KM
    min_lat, max_lat, min_lng, max_lng = _bounding_box(lat, lng, radius_km)

    # Generous fetch pool for the ranker
    fetch_limit = min(limit * 4, 400)

    stmt = text("""
        SELECT id,
               ((:lat - lat) * (:lat - lat) + (:lng - lng) * (:lng - lng)) AS dist2
        FROM places
        WHERE is_active = 1
          AND lat BETWEEN :min_lat AND :max_lat
          AND lng BETWEEN :min_lng AND :max_lng
        ORDER BY dist2 ASC, rank_score DESC
        LIMIT :limit OFFSET :offset
    """)

    count_stmt = text("""
        SELECT COUNT(*)
        FROM places
        WHERE is_active = 1
          AND lat BETWEEN :min_lat AND :max_lat
          AND lng BETWEEN :min_lng AND :max_lng
    """)

    params = {
        "lat": lat, "lng": lng,
        "min_lat": min_lat, "max_lat": max_lat,
        "min_lng": min_lng, "max_lng": max_lng,
        "limit": fetch_limit, "offset": offset,
    }

    total = db.execute(count_stmt, params).scalar_one_or_none() or 0
    rows = db.execute(stmt, params).fetchall()

    if not rows:
        return [], int(total)

    ids = [r[0] for r in rows]
    place_map = {
        p.id: p
        for p in db.query(Place).filter(Place.id.in_(ids)).all()
    }

    # Return in proximity order (rank_feed will re-rank with blended score)
    ordered = [place_map[pid] for pid in ids if pid in place_map]
    return ordered, int(total)
