"""
Lightweight data quality checks for CRAVE.

All functions return summary dicts (safe to log/report).
All queries are read-only — no writes.
"""
from __future__ import annotations

from typing import Dict, Any
from sqlalchemy import select, func, text, exists, not_, or_
from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.db.models.place_image import PlaceImage


def check_image_quality(db: Session) -> Dict[str, Any]:
    """Check primary image coverage and orphan detection."""
    total_active = db.scalar(select(func.count(Place.id)).where(Place.is_active.is_(True)))

    # Places with no primary image
    no_primary = db.scalar(
        select(func.count(Place.id)).where(
            Place.is_active.is_(True),
            not_(exists(
                select(PlaceImage.id).where(
                    PlaceImage.place_id == Place.id,
                    PlaceImage.is_primary.is_(True)
                )
            ))
        )
    )

    # Places with zero images
    no_images = db.scalar(
        select(func.count(Place.id)).where(
            Place.is_active.is_(True),
            not_(exists(
                select(PlaceImage.id).where(PlaceImage.place_id == Place.id)
            ))
        )
    )

    # Places with multiple primary images
    multi_primary_result = db.execute(
        select(PlaceImage.place_id, func.count(PlaceImage.id).label("cnt"))
        .where(PlaceImage.is_primary.is_(True))
        .group_by(PlaceImage.place_id)
        .having(func.count(PlaceImage.id) > 1)
    ).all()

    return {
        "total_active_places": total_active,
        "places_no_primary_image": no_primary,
        "places_no_images": no_images,
        "places_multi_primary": len(multi_primary_result),
        "coverage_pct": round((total_active - no_primary) / total_active * 100, 1) if total_active else 0,
    }


def check_score_distribution(db: Session) -> Dict[str, Any]:
    """Check rank_score distribution across active places."""
    results = db.execute(
        text("""
        SELECT
          CASE
            WHEN rank_score < 0.5 THEN 'below_0.5'
            WHEN rank_score < 0.6 THEN '0.5-0.6'
            WHEN rank_score < 0.7 THEN '0.6-0.7'
            WHEN rank_score < 0.8 THEN '0.7-0.8'
            WHEN rank_score < 0.9 THEN '0.8-0.9'
            ELSE '0.9+'
          END as bucket,
          COUNT(*) as cnt
        FROM places WHERE is_active=1
        GROUP BY 1 ORDER BY 1
        """)
    ).all()

    avg_score = db.scalar(
        select(func.avg(Place.rank_score)).where(Place.is_active.is_(True))
    )

    return {
        "buckets": {r.bucket: r.cnt for r in results},
        "avg_score": round(float(avg_score or 0), 4),
    }


def check_signal_coverage(db: Session) -> Dict[str, Any]:
    """Check what % of places have each key signal."""
    total = db.scalar(select(func.count(Place.id)).where(Place.is_active.is_(True)))

    has_grubhub = db.scalar(
        select(func.count(Place.id)).where(
            Place.is_active.is_(True),
            Place.grubhub_url.isnot(None)
        )
    )
    has_website = db.scalar(
        select(func.count(Place.id)).where(
            Place.is_active.is_(True),
            Place.website.isnot(None)
        )
    )
    has_menu_source = db.scalar(
        select(func.count(Place.id)).where(
            Place.is_active.is_(True),
            Place.menu_source_url.isnot(None)
        )
    )

    return {
        "total_active": total,
        "has_grubhub_url": has_grubhub,
        "has_website": has_website,
        "has_menu_source_url": has_menu_source,
        "grubhub_pct": round(has_grubhub / total * 100, 1) if total else 0,
        "website_pct": round(has_website / total * 100, 1) if total else 0,
        "menu_source_pct": round(has_menu_source / total * 100, 1) if total else 0,
    }
