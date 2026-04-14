"""
Trending places endpoint.

Trending is computed from:
- hitlist velocity (saves in last 24h vs total) — weight 0.50
- rank_score (quality baseline) — weight 0.30
- recency (days since last update) — weight 0.20

No fake data. All signals are real.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.place import Place
from app.db.models.hitlist_save import HitlistSave
from app.api.v1.schemas.places import PlaceOut, PlacesResponse
from app.services.cache.response_cache import response_cache
from app.services.query.place_image_query import get_primary_image_urls_bulk

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trending", tags=["trending"])

UTC = timezone.utc
TRENDING_CACHE_TTL = 300  # 5 minutes


def _trending_cache_key(city_id: str, limit: int) -> str:
    return f"trending:{city_id}:{limit}"


@router.get("", response_model=PlacesResponse, summary="Trending places")
def get_trending(
    city_id: str = Query(..., description="City UUID"),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
) -> PlacesResponse:
    """
    Returns trending places for a city.

    Trending score = (hitlist_velocity * 0.50) + (rank_score * 0.30) + (recency * 0.20)

    hitlist_velocity = saves in last 24h / total saves (0.0 if no hitlist data)
    recency = 1.0 - (days_since_update / 90.0), clamped to [0, 1]
    """
    cache_key = _trending_cache_key(city_id, limit)
    try:
        cached = response_cache.get(cache_key)
        if cached is not None:
            return cached
    except Exception as exc:
        logger.debug("trending_cache_read_failed error=%s", exc)

    now = datetime.now(UTC)
    cutoff_24h = now - timedelta(hours=24)

    try:
        # Get active places for this city (score top 500, return top N)
        places = db.execute(
            select(Place)
            .where(Place.is_active.is_(True), Place.city_id == city_id)
            .limit(500)
        ).scalars().all()

        if not places:
            return PlacesResponse(total=0, page=1, page_size=limit, items=[])

        place_id_set = {p.id for p in places}

        # Get all hitlist saves for these places (compute velocity in Python)
        try:
            all_saves = db.execute(
                select(HitlistSave.place_id, HitlistSave.created_at)
                .where(HitlistSave.place_id.in_(place_id_set))
            ).all()

            # Build hitlist map: place_id -> {total, recent}
            hitlist_map: dict = {}
            cutoff_naive = cutoff_24h.replace(tzinfo=None)
            for row in all_saves:
                pid = row.place_id
                if pid not in hitlist_map:
                    hitlist_map[pid] = {"total": 0, "recent": 0}
                hitlist_map[pid]["total"] += 1
                created = row.created_at
                # Handle timezone-naive datetimes (SQLite stores naive)
                if created is not None:
                    if created.tzinfo is not None:
                        created = created.replace(tzinfo=None)
                    if created >= cutoff_naive:
                        hitlist_map[pid]["recent"] += 1
        except Exception:
            hitlist_map = {}

        # Compute trending score for each place
        scored = []
        for p in places:
            rank = float(p.rank_score or 0.0)

            # Recency score
            updated = getattr(p, "updated_at", None)
            if updated:
                if updated.tzinfo is not None:
                    updated = updated.replace(tzinfo=None)
                now_naive = now.replace(tzinfo=None)
                days_old = max(0, (now_naive - updated).days)
                recency = max(0.0, 1.0 - days_old / 90.0)
            else:
                recency = 0.0

            # Hitlist velocity
            h = hitlist_map.get(p.id, {})
            total_saves = h.get("total", 0)
            recent_saves = h.get("recent", 0)
            if total_saves > 0:
                velocity = recent_saves / total_saves
            else:
                velocity = 0.0

            trending = (velocity * 0.50) + (rank * 0.30) + (recency * 0.20)
            scored.append((p, trending))

        # Sort by trending score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        top_places = [p for p, _ in scored[:limit]]

        # Bulk image lookup
        place_ids = [p.id for p in top_places]
        image_urls = get_primary_image_urls_bulk(db, place_ids=place_ids)

        items = []
        for p in top_places:
            try:
                p.primary_image_url = image_urls.get(p.id)
                items.append(PlaceOut.model_validate(p, from_attributes=True))
            except Exception as exc:
                logger.debug("trending_serialize_failed place_id=%s error=%s", p.id, exc)

        response = PlacesResponse(
            total=len(items),
            page=1,
            page_size=limit,
            items=items,
        )

        try:
            response_cache.set(cache_key, response, TRENDING_CACHE_TTL)
        except Exception as exc:
            logger.debug("trending_cache_write_failed error=%s", exc)

        return response

    except Exception as exc:
        logger.exception("trending_query_failed city_id=%s error=%s", city_id, exc)
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
