# app/api/v1/routes/data_pipeline_admin.py
"""
Admin-only data-pipeline control-room endpoints.

This is intentionally read-only. It gives operators one truthful place to see
whether menu/photo population is blocked by provider access, waiting for manual
evidence review, missing provenance, or simply not running. Running production
jobs remains an explicit ops action, not something a dashboard GET endpoint
should trigger.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.v1.routes.moderation import require_admin
from app.core.auth import require_api_key
from app.core.rate_limit import rate_limit
from app.db.models.job_run import JobRun
from app.db.models.menu_source import MenuSource
from app.db.models.menu_submission import (
    STATUS_APPROVED,
    STATUS_PENDING,
    STATUS_REJECTED,
    MenuSubmission,
)
from app.db.models.place_image import PlaceImage
from app.db.session import get_db

router = APIRouter(prefix="/moderation/data-pipeline", tags=["data-pipeline"])

PROVIDER_API_REQUIRED = "access_blocked:provider_api_required"


def _count(db: Session, *criteria: Any) -> int:
    query = db.query(func.count()).select_from(MenuSource)
    if criteria:
        query = query.filter(*criteria)
    return int(query.scalar() or 0)


def _count_model(db: Session, model: Any, *criteria: Any) -> int:
    query = db.query(func.count()).select_from(model)
    if criteria:
        query = query.filter(*criteria)
    return int(query.scalar() or 0)


def _group_counts(db: Session, model: Any, column: Any) -> dict[str, int]:
    rows = (
        db.query(column, func.count())
        .select_from(model)
        .group_by(column)
        .order_by(func.count().desc())
        .all()
    )
    return {str(key or "unknown"): int(count or 0) for key, count in rows}


def _submission_count(db: Session, status: str, *, with_evidence: bool = False) -> int:
    criteria: list[Any] = [MenuSubmission.status == status]
    if with_evidence:
        criteria.append(
            or_(
                MenuSubmission.evidence_url.isnot(None),
                MenuSubmission.evidence_image_id.isnot(None),
                MenuSubmission.evidence_note.isnot(None),
            )
        )
    return _count_model(db, MenuSubmission, *criteria)


def _source_is_provider_blocked() -> Any:
    return or_(
        MenuSource.last_failure_reason == PROVIDER_API_REQUIRED,
        MenuSource.invalidation_reason == PROVIDER_API_REQUIRED,
    )


def _latest_job(db: Session, job_name: str) -> dict[str, Any] | None:
    row = (
        db.query(JobRun)
        .filter(JobRun.job_name == job_name)
        .order_by(JobRun.started_at.desc())
        .first()
    )
    if not row:
        return None
    return {
        "id": row.id,
        "job_name": row.job_name,
        "started_at": row.started_at,
        "finished_at": row.finished_at,
        "success": row.success,
        "summary": row.summary,
        "error": row.error,
    }


@router.get(
    "/dashboard",
    dependencies=[Depends(rate_limit), Depends(require_api_key)],
)
def data_pipeline_dashboard(
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
    recent_limit: int = Query(10, ge=1, le=50),
):
    """
    Read-only status for menu/photo population.

    The frontend/admin console can render this directly; scripts can also use
    it as a preflight before running canaries or backfills.
    """

    recent_failures = (
        db.query(MenuSource)
        .filter(
            or_(
                MenuSource.last_failure_reason.isnot(None),
                MenuSource.invalidation_reason.isnot(None),
            )
        )
        .order_by(MenuSource.last_failure_at.desc(), MenuSource.updated_at.desc())
        .limit(recent_limit)
        .all()
    )

    pending_submissions = (
        db.query(MenuSubmission)
        .filter(MenuSubmission.status == STATUS_PENDING)
        .order_by(MenuSubmission.created_at.asc())
        .limit(recent_limit)
        .all()
    )

    oldest_pending = (
        db.query(MenuSubmission.created_at)
        .filter(MenuSubmission.status == STATUS_PENDING)
        .order_by(MenuSubmission.created_at.asc())
        .first()
    )

    return {
        "menu_sources": {
            "total": _count(db),
            "active": _count(db, MenuSource.is_active.is_(True)),
            "inactive": _count(db, MenuSource.is_active.is_(False)),
            "failed": _count(
                db,
                or_(
                    MenuSource.last_failure_reason.isnot(None),
                    MenuSource.invalidation_reason.isnot(None),
                ),
            ),
            "provider_access_required": _count(db, _source_is_provider_blocked()),
            "by_provider": _group_counts(db, MenuSource, MenuSource.provider),
            "by_type": _group_counts(db, MenuSource, MenuSource.source_type),
            "recent_failures": [
                {
                    "id": source.id,
                    "place_id": source.place_id,
                    "source_url": source.source_url,
                    "provider": source.provider,
                    "source_type": source.source_type,
                    "is_active": source.is_active,
                    "failure_count": source.failure_count,
                    "last_failure_at": source.last_failure_at,
                    "last_failure_reason": source.last_failure_reason,
                    "invalidation_reason": source.invalidation_reason,
                }
                for source in recent_failures
            ],
        },
        "menu_submissions": {
            "pending": _submission_count(db, STATUS_PENDING),
            "approved": _submission_count(db, STATUS_APPROVED),
            "rejected": _submission_count(db, STATUS_REJECTED),
            "pending_with_evidence": _submission_count(
                db, STATUS_PENDING, with_evidence=True
            ),
            "oldest_pending_at": oldest_pending[0] if oldest_pending else None,
            "recent_pending": [
                {
                    "id": submission.id,
                    "place_id": submission.place_id,
                    "submitted_by": submission.submitted_by,
                    "item_count": len(submission.items or []),
                    "created_at": submission.created_at,
                    "has_evidence": bool(
                        submission.evidence_url
                        or submission.evidence_image_id
                        or submission.evidence_note
                    ),
                    "evidence_url": submission.evidence_url,
                    "evidence_image_id": submission.evidence_image_id,
                }
                for submission in pending_submissions
            ],
        },
        "image_sources": {
            "total": _count_model(db, PlaceImage),
            "with_provenance": _count_model(
                db,
                PlaceImage,
                or_(
                    PlaceImage.source_provider.isnot(None),
                    PlaceImage.source_context.isnot(None),
                    PlaceImage.source_metadata.isnot(None),
                ),
            ),
            "missing_provenance": _count_model(
                db,
                PlaceImage,
                PlaceImage.source_provider.is_(None),
                PlaceImage.source_context.is_(None),
                PlaceImage.source_metadata.is_(None),
            ),
            "by_provider": _group_counts(db, PlaceImage, PlaceImage.source_provider),
        },
        "jobs": {
            "menu_enrichment": _latest_job(db, "menu_enrichment"),
            "image_ingestion": _latest_job(db, "image_ingestion"),
            "osm_hours_outdoor_backfill": _latest_job(
                db, "osm_hours_outdoor_backfill"
            ),
        },
    }
