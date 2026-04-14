"""
Enrichment priority and coverage endpoints.

These endpoints help identify which places need data the most,
so enrichment efforts can be directed at highest-impact gaps.
"""
from __future__ import annotations

import logging
from typing import Optional, List
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func, text, exists, not_
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.place import Place
from app.db.models.place_image import PlaceImage
from app.db.models.place_claim import PlaceClaim
from app.db.models.place_signal import PlaceSignal
from app.db.models.hitlist_save import HitlistSave

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/enrichment", tags=["enrichment"])

UTC = timezone.utc


class EnrichmentTarget(BaseModel):
    place_id: str
    name: str
    city_id: str
    rank_score: float
    missing: List[str]          # list of gaps: "website", "menu", "social", "images"
    priority_score: float       # 0.0-1.0, higher = needs enrichment more


class EnrichmentPriorityResponse(BaseModel):
    total: int
    city_id: Optional[str]
    targets: List[EnrichmentTarget]


@router.get("/priority", response_model=EnrichmentPriorityResponse)
def get_enrichment_priority(
    city_id: Optional[str] = Query(None, description="Filter by city UUID"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> EnrichmentPriorityResponse:
    """
    Returns places that would benefit most from additional data collection.

    Priority score is higher for:
    - High rank_score places (more users will see them)
    - Places missing multiple signals
    - Places missing the highest-weight signals (menu, website)
    """
    stmt = select(Place).where(Place.is_active.is_(True))
    if city_id:
        stmt = stmt.where(Place.city_id == city_id)
    stmt = stmt.order_by(Place.rank_score.desc()).limit(500)

    places = db.execute(stmt).scalars().all()

    # Bulk check: which places have images
    place_ids = [p.id for p in places]

    has_image_set = set(
        r[0] for r in db.execute(
            select(PlaceImage.place_id)
            .where(PlaceImage.place_id.in_(place_ids), PlaceImage.is_primary.is_(True))
        ).all()
    )

    has_menu_set = set(
        r[0] for r in db.execute(
            select(PlaceClaim.place_id)
            .where(PlaceClaim.place_id.in_(place_ids), PlaceClaim.field == "menu_item")
            .distinct()
        ).all()
    )

    has_signal_set = set(
        r[0] for r in db.execute(
            select(PlaceSignal.place_id)
            .where(PlaceSignal.place_id.in_(place_ids))
            .distinct()
        ).all()
    )

    targets = []
    for p in places:
        missing = []
        if p.id not in has_image_set:
            missing.append("images")
        if not p.website and not p.grubhub_url:
            missing.append("website")
        if p.id not in has_menu_set:
            missing.append("menu")
        if p.id not in has_signal_set:
            missing.append("social")

        if not missing:
            continue  # place is fully enriched, skip

        # Priority score: rank * gap_weight
        # Higher rank + more gaps = higher priority
        gap_weights = {
            "menu": 0.35,      # menu_score is highest-weight signal (0.28)
            "website": 0.25,   # completeness_score depends on this
            "social": 0.20,    # creator/awards/blog
            "images": 0.20,    # image_score
        }
        gap_score = sum(gap_weights.get(g, 0.1) for g in missing)
        rank = float(p.rank_score or 0.0)
        priority = min(1.0, (rank * 0.5) + (gap_score * 0.5))

        targets.append(EnrichmentTarget(
            place_id=p.id,
            name=p.name or "",
            city_id=p.city_id or "",
            rank_score=rank,
            missing=missing,
            priority_score=round(priority, 4),
        ))

    # Sort by priority (highest first)
    targets.sort(key=lambda t: t.priority_score, reverse=True)
    targets = targets[:limit]

    return EnrichmentPriorityResponse(
        total=len(targets),
        city_id=city_id,
        targets=targets,
    )


# ---------------------------------------------------------------------------
# Coverage summary
# ---------------------------------------------------------------------------

class SignalCoverage(BaseModel):
    signal: str
    places_covered: int
    total_places: int
    coverage_pct: float
    status: str  # "ACTIVE", "WIRED_AWAITING_DATA", "NOT_WIRED"


class CoverageSummaryResponse(BaseModel):
    total_active_places: int
    generated_at: str
    coverage: List[SignalCoverage]
    enrichment_gap_pct: float  # % of places missing at least one high-value signal


router_coverage = APIRouter(prefix="/coverage", tags=["coverage"])


@router_coverage.get("/summary", response_model=CoverageSummaryResponse)
def get_coverage_summary(db: Session = Depends(get_db)) -> CoverageSummaryResponse:
    """
    Returns signal coverage statistics across all active places.
    """
    total = db.scalar(select(func.count(Place.id)).where(Place.is_active.is_(True))) or 0

    if total == 0:
        return CoverageSummaryResponse(
            total_active_places=0,
            generated_at=datetime.now(UTC).isoformat(),
            coverage=[],
            enrichment_gap_pct=0.0,
        )

    # Image coverage
    img_count = db.scalar(
        select(func.count(func.distinct(PlaceImage.place_id)))
        .select_from(PlaceImage)
        .join(Place, Place.id == PlaceImage.place_id)
        .where(Place.is_active.is_(True), PlaceImage.is_primary.is_(True))
    ) or 0

    # Menu coverage
    menu_count = db.scalar(
        select(func.count(func.distinct(PlaceClaim.place_id)))
        .select_from(PlaceClaim)
        .join(Place, Place.id == PlaceClaim.place_id)
        .where(Place.is_active.is_(True), PlaceClaim.field == "menu_item")
    ) or 0

    # Website / grubhub
    website_count = db.scalar(
        select(func.count(Place.id))
        .where(Place.is_active.is_(True), Place.website.isnot(None))
    ) or 0

    grubhub_count = db.scalar(
        select(func.count(Place.id))
        .where(Place.is_active.is_(True), Place.grubhub_url.isnot(None))
    ) or 0

    # PlaceSignal coverage by type
    signal_counts = dict(
        db.execute(
            select(PlaceSignal.signal_type, func.count(func.distinct(PlaceSignal.place_id)))
            .group_by(PlaceSignal.signal_type)
        ).all()
    )

    def pct(n: int) -> float:
        return round(n / total * 100, 1) if total else 0.0

    coverage = [
        SignalCoverage(signal="image_score", places_covered=img_count, total_places=total, coverage_pct=pct(img_count), status="ACTIVE"),
        SignalCoverage(signal="menu_score", places_covered=menu_count, total_places=total, coverage_pct=pct(menu_count), status="ACTIVE"),
        SignalCoverage(signal="app_score (grubhub)", places_covered=grubhub_count, total_places=total, coverage_pct=pct(grubhub_count), status="ACTIVE"),
        SignalCoverage(signal="completeness_score (website)", places_covered=website_count, total_places=total, coverage_pct=pct(website_count), status="ACTIVE"),
        SignalCoverage(signal="creator_score", places_covered=signal_counts.get("creator", 0), total_places=total, coverage_pct=pct(signal_counts.get("creator", 0)), status="WIRED_AWAITING_DATA"),
        SignalCoverage(signal="awards_score", places_covered=signal_counts.get("award", 0), total_places=total, coverage_pct=pct(signal_counts.get("award", 0)), status="WIRED_AWAITING_DATA"),
        SignalCoverage(signal="blog_score", places_covered=signal_counts.get("blog", 0), total_places=total, coverage_pct=pct(signal_counts.get("blog", 0)), status="WIRED_AWAITING_DATA"),
    ]

    # Places missing at least one high-value signal (menu OR grubhub)
    fully_enriched = db.scalar(
        select(func.count(func.distinct(Place.id)))
        .select_from(Place)
        .where(
            Place.is_active.is_(True),
            Place.grubhub_url.isnot(None),
            exists(
                select(PlaceClaim.place_id)
                .where(PlaceClaim.place_id == Place.id, PlaceClaim.field == "menu_item")
            ),
        )
    ) or 0

    enrichment_gap_pct = round((total - fully_enriched) / total * 100, 1) if total else 0.0

    return CoverageSummaryResponse(
        total_active_places=total,
        generated_at=datetime.now(UTC).isoformat(),
        coverage=coverage,
        enrichment_gap_pct=enrichment_gap_pct,
    )
