# app/workers/recompute_scores_worker.py
from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Set

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.place import Place
from app.db.models.place_image import PlaceImage
from app.db.models.place_signal import PlaceSignal
from app.services.scoring.signal_context import SignalContext
from app.services.scoring.place_score_v4 import compute_place_score_v4
from app.services.cache.response_cache import response_cache
from app.services.cache.cache_keys import _norm
from app.services.feed.feed_bucket_store import invalidate_bucket

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]
QUEUE_FILE = BASE_DIR / "var" / "queue" / "recompute_scores.queue"

UTC = timezone.utc

SIGNAL_DECAY_DAYS: Dict[str, int] = {
    "creator": 30,
    "award": 365,
    "blog": 180,
    "review": 730,
    "save": 730,
}
DEFAULT_DECAY_DAYS = 180


def _compute_decayed_signal_scores(
    rows: list,
    signal_types: list,
    now: datetime,
) -> Dict[str, Dict[str, float]]:
    """
    Returns {signal_type: {place_id: decayed_score}}.

    Applies exponential-style linear decay per signal type so that older
    signals contribute less to a place's score.
    """
    grouped: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))

    for row in rows:
        place_id = row.place_id
        sig_type = row.signal_type
        value = row.value
        created_at = row.created_at

        if sig_type not in signal_types:
            continue

        # Normalize created_at — SQLite may return a string
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except ValueError:
                created_at = now  # treat as fresh if unparseable
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        decay_days = SIGNAL_DECAY_DAYS.get(sig_type, DEFAULT_DECAY_DAYS)
        days_old = max(0, (now - created_at).days)
        decay_factor = max(0.05, 1.0 - days_old / decay_days)
        effective = float(value) * decay_factor
        grouped[sig_type][place_id].append(effective)

    result: Dict[str, Dict[str, float]] = {}
    for sig_type in signal_types:
        result[sig_type] = {
            place_id: min(sum(vals) / len(vals), 1.0)
            for place_id, vals in grouped[sig_type].items()
        }
    return result


@dataclass(frozen=True)
class Job:
    type: str
    created_at: str
    payload: Dict[str, Any]


def _read_jobs() -> list[Job]:
    if not QUEUE_FILE.exists():
        return []
    raw = QUEUE_FILE.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    return [
        Job(
            type=str(d.get("type")),
            created_at=str(d.get("created_at")),
            payload=dict(d.get("payload") or {}),
        )
        for d in (json.loads(line) for line in raw.splitlines())
    ]


def _clear_queue() -> None:
    QUEUE_FILE.write_text("", encoding="utf-8")


def _fetch_signal_context(db: Session, place_ids: list[str]) -> SignalContext:
    """Batch-fetch all signal data. One query per signal type — never per-place."""
    if not place_ids:
        return SignalContext()

    # Image counts per place
    image_rows = db.execute(
        select(PlaceImage.place_id, func.count(PlaceImage.id).label("cnt"))
        .where(PlaceImage.place_id.in_(place_ids))
        .group_by(PlaceImage.place_id)
    ).all()
    image_counts = {r.place_id: r.cnt for r in image_rows}

    # Places with a primary image
    primary_rows = db.execute(
        select(PlaceImage.place_id)
        .where(
            PlaceImage.place_id.in_(place_ids),
            PlaceImage.is_primary.is_(True),
        )
    ).all()
    has_primary = {r.place_id for r in primary_rows}

    # Menu item counts from PlaceClaim (where field="menu_item")
    # The menu pipeline writes PlaceClaim rows with field="menu_item", NOT menu_items table
    menu_counts: Dict[str, int] = {}
    try:
        from app.db.models.place_claim import PlaceClaim
        menu_claim_rows = db.execute(
            select(PlaceClaim.place_id, func.count(PlaceClaim.id).label("cnt"))
            .where(
                PlaceClaim.place_id.in_(place_ids),
                PlaceClaim.field == "menu_item",
            )
            .group_by(PlaceClaim.place_id)
        ).all()
        menu_counts = {r.place_id: r.cnt for r in menu_claim_rows}
    except Exception:
        pass

    # Hitlist velocity scores — places that have been saved to hitlists
    hitlist_scores: Dict[str, float] = {}
    try:
        from app.db.models.hitlist_save import HitlistSave
        hitlist_rows = db.execute(
            select(HitlistSave.place_id, func.count(HitlistSave.id).label("cnt"))
            .where(
                HitlistSave.place_id.in_(place_ids),
                HitlistSave.place_id.isnot(None),
            )
            .group_by(HitlistSave.place_id)
        ).all()
        hitlist_scores = {r.place_id: min(float(r.cnt) / 100.0, 1.0) for r in hitlist_rows}
    except Exception:
        pass

    # Fetch ALL signal rows for creator/award/blog in one query, then compute
    # time-decayed weighted averages in Python.
    PS = PlaceSignal
    signal_rows = db.execute(
        select(PS.place_id, PS.signal_type, PS.value, PS.created_at)
        .where(
            PS.place_id.in_(place_ids),
            PS.signal_type.in_(["creator", "award", "blog"]),
        )
    ).all()

    now = datetime.now(UTC)
    decayed = _compute_decayed_signal_scores(signal_rows, ["creator", "award", "blog"], now)

    creator_scores: Dict[str, float] = decayed.get("creator", {})
    awards_scores: Dict[str, float] = decayed.get("award", {})
    blog_scores: Dict[str, float] = decayed.get("blog", {})

    # Count distinct creator SOURCES per place (for consensus gate in v4).
    # Deduplicate by provider so a single source with multiple rows still counts as 1.
    _creator_sources: Dict[str, set] = {}
    for row in signal_rows:
        if row.signal_type == "creator":
            _creator_sources.setdefault(row.place_id, set()).add(row.provider)
    creator_mention_counts: Dict[str, int] = {pid: len(s) for pid, s in _creator_sources.items()}

    # Count distinct blog SOURCES per place (for blog consensus gate in v4).
    # Same provider-dedup logic: one blog source = one mention regardless of row count.
    _blog_sources: Dict[str, set] = {}
    for row in signal_rows:
        if row.signal_type == "blog":
            _blog_sources.setdefault(row.place_id, set()).add(row.provider)
    blog_mention_counts: Dict[str, int] = {pid: len(s) for pid, s in _blog_sources.items()}

    # Weak creator_score baseline: detect social platform URLs in place.website.
    # This gives 0.30 to places whose website IS a social profile, indicating
    # creator-driven discovery. Overridden by any higher signal from PlaceSignal.
    _SOCIAL_DOMAINS = ("instagram.com", "tiktok.com", "youtube.com", "linktr.ee", "linktree.com")
    social_url_rows = db.execute(
        select(Place.id, Place.website)
        .where(
            Place.id.in_(place_ids),
            Place.website.isnot(None),
            Place.website != "",
        )
    ).all()
    for row in social_url_rows:
        website = (row.website or "").lower()
        if any(d in website for d in _SOCIAL_DOMAINS):
            # Only set baseline if no stronger PlaceSignal-derived value already
            if row.id not in creator_scores or creator_scores[row.id] < 0.30:
                creator_scores[row.id] = 0.30

    return SignalContext(
        image_counts=image_counts,
        has_primary=has_primary,
        menu_item_counts=menu_counts,
        hitlist_scores=hitlist_scores,
        creator_scores=creator_scores,
        creator_mention_counts=creator_mention_counts,
        awards_scores=awards_scores,
        blog_scores=blog_scores,
        blog_mention_counts=blog_mention_counts,
    )


def _clamp_limit(limit: Optional[int]) -> Optional[int]:
    if limit is None:
        return None
    try:
        return max(1, int(limit))
    except Exception:
        return None


def _iter_place_batches(
    db: Session,
    *,
    city_id: Optional[str],
    limit: Optional[int],
    batch_size: int = 500,
):
    limit = _clamp_limit(limit)
    stmt = select(Place).order_by(Place.id.asc())
    if city_id:
        stmt = stmt.where(Place.city_id == city_id)

    offset = 0
    processed = 0

    while True:
        batch = db.execute(stmt.limit(batch_size).offset(offset)).scalars().all()
        if not batch:
            break
        if limit is not None:
            remaining = limit - processed
            if remaining <= 0:
                break
            batch = batch[:remaining]

        yield batch
        processed += len(batch)
        offset += batch_size
        if limit is not None and processed >= limit:
            break


def _score_batch(db: Session, places: list[Place]) -> tuple[int, Set[str]]:
    place_ids = [p.id for p in places]
    ctx = _fetch_signal_context(db, place_ids)

    now = datetime.now(timezone.utc)
    updated = 0
    city_ids: Set[str] = set()

    for place in places:
        pid = place.id

        # Track city IDs for cache invalidation
        if place.city_id:
            city_ids.add(place.city_id)

        # Resolve city slug for city-aware weights
        city_slug: Optional[str] = None
        city = getattr(place, "city", None)
        if city:
            city_slug = getattr(city, "slug", None) or getattr(city, "name", None)

        result = compute_place_score_v4(
            place_id=pid,
            name=place.name or "",
            lat=place.lat,
            lng=place.lng,
            has_menu=bool(place.has_menu),
            website=place.website,
            updated_at=place.updated_at,
            grubhub_url=place.grubhub_url,
            menu_source_url=place.menu_source_url,
            image_count=ctx.image_count(pid),
            has_primary_image=ctx.has_primary_image(pid),
            menu_item_count=ctx.menu_item_count(pid),
            hitlist_score=ctx.hitlist_score(pid),
            creator_score=ctx.creator_score(pid),
            creator_mention_count=ctx.creator_mention_count(pid),
            awards_score=ctx.awards_score(pid),
            blog_score=ctx.blog_score(pid),
            blog_mention_count=ctx.blog_mention_count(pid),
            city_slug=city_slug,
        )

        place.master_score = result.final_score
        place.rank_score = result.final_score
        # Only set last_scored_at if the column exists
        if hasattr(place, "last_scored_at"):
            place.last_scored_at = now
        updated += 1

    return updated, city_ids


def _invalidate_cache_for_cities(affected_cities: Set[str]) -> None:
    """Invalidate feed and map cache entries for the given set of city IDs."""
    city_norms = {_norm(city_id) for city_id in affected_cities}

    for city_norm in city_norms:
        # Feed keys: feed:{city}:{page}:{page_size} — prefix covers all pages/sizes
        response_cache.delete_prefix(f"feed:{city_norm}:")

    # Map keys: map:{lat}:{lng}:{radius}:{limit}:{city}:{cat}
    # City is not a prefix segment, so scan for :{city_norm}: substring in map keys
    with response_cache._lock:
        to_delete = [
            k for k in response_cache._store
            if k.startswith("map:") and any(f":{cn}:" in k for cn in city_norms)
        ]
        for k in to_delete:
            del response_cache._store[k]

    # Also clear feed buckets so next request rebuilds with updated scores
    for city_id in affected_cities:
        invalidate_bucket(city_id)
    invalidate_bucket(None)  # global bucket

    logger.info("cache_invalidated_after_recompute cities=%s", affected_cities)


def run_worker_once() -> int:
    jobs = _read_jobs()
    if not jobs:
        return 0

    _clear_queue()
    db = SessionLocal()
    total_updated = 0
    affected_cities: Set[str] = set()

    try:
        for job in jobs:
            if job.type != "recompute_scores":
                continue

            city_id = job.payload.get("city_id")
            limit = job.payload.get("limit")

            for batch in _iter_place_batches(db, city_id=city_id, limit=limit):
                updated, batch_cities = _score_batch(db, batch)
                total_updated += updated
                affected_cities.update(batch_cities)
                db.commit()

        if affected_cities:
            _invalidate_cache_for_cities(affected_cities)

        return total_updated

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()
