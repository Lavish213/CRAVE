from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.orm import Session

from app.db.models.place import Place


def build_feed(
    db: Session,
    *,
    lat: float,
    lng: float,
    radius_km: float,
    limit: int,
) -> Dict[str, Any]:
    """
    Fallback feed builder for map + feed systems.

    Always returns places even if geo filtering fails.
    """

    try:
        rows = (
            db.query(Place)
            .filter(
                Place.is_active.is_(True),
                Place.lat.isnot(None),
                Place.lng.isnot(None),
            )
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
            "places": [],
        }

    places = []

    for p in rows:
        try:
            places.append(
                {
                    "id": p.id,
                    "name": p.name,
                    "lat": float(p.lat),
                    "lng": float(p.lng),
                    "city_id": p.city_id,
                    "price_tier": p.price_tier,
                    "rank_score": float(p.rank_score or 0),
                    "primary_image_url": None,
                }
            )
        except Exception:
            continue

    return {
        "ok": True,
        "places": places,
    }