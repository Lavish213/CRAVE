"""
"My places" map layer — the personal, curated map both Beli and Biter
advertise as a core feature, which CRAVE's Map tab never had (it only
ever showed the global catalog). Reuses the existing saves data
(HitlistSave, dedup_key="save:{user_id}:{place_id}" — see
app/api/v1/routes/saves.py) rather than a new table.
"""
from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.hitlist_save import HitlistSave
from app.db.models.place import Place

_DEDUP_PREFIX = "save"


def get_saved_places_geojson(db: Session, *, user_id: str) -> Dict[str, Any]:
    """
    Unlike fetch_places_for_map/_geojson, this is never viewport/bounding-
    box scoped — a personal saved list is small enough to just return in
    full and let the client fit the map to it. Every feature's tier is
    fixed to "default" rather than reusing map_query's percentile-based
    tier assignment: computed over a handful of personal saves, a
    percentile tier wouldn't mean anything (your only saved place would
    trivially be "elite"). The frontend renders this layer in one
    consistent "saved" color regardless of tier.
    """
    saves = (
        db.query(HitlistSave)
        .filter(
            HitlistSave.user_id == user_id,
            HitlistSave.place_id.isnot(None),
            HitlistSave.dedup_key.like(f"{_DEDUP_PREFIX}:%"),
        )
        .all()
    )

    place_ids = [s.place_id for s in saves if s.place_id]
    if not place_ids:
        return {"type": "FeatureCollection", "features": []}

    places = db.execute(
        select(Place).where(
            Place.id.in_(place_ids),
            Place.is_active.is_(True),
            Place.lat.isnot(None),
            Place.lng.isnot(None),
        )
    ).scalars().all()

    features: List[Dict[str, Any]] = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [p.lng, p.lat]},
            "properties": {
                "id": p.id,
                "name": p.name,
                "city_id": p.city_id,
                "tier": "default",
                "rank_score": float(p.rank_score or 0.0),
                "price_tier": p.price_tier,
                "primary_image_url": None,
                "category": None,
                "has_menu": bool(p.has_menu),
            },
        }
        for p in places
    ]

    return {"type": "FeatureCollection", "features": features}
