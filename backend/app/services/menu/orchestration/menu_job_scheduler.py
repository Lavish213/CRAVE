from __future__ import annotations

import logging
from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from app.db.models.enrichment_job import EnrichmentJob
from app.db.models.place import Place


logger = logging.getLogger(__name__)

ACTIVE_MENU_JOB_STATUSES = ("pending", "running")

HIGH_PRIORITY = 10
NORMAL_PRIORITY = 1


def ensure_single_active_job(
    db: Session,
    place_id: str,
    job_type: str = "menu",
) -> Optional[EnrichmentJob]:
    """
    Guarantee at most one is_active=True job per (place_id, job_type).

    - If multiple active jobs exist: deactivate all but the highest-priority/newest.
    - If multiple inactive jobs exist: delete stale extras so only one is_active=False
      row occupies the constraint slot (prevents future insert conflicts).
    - Returns the surviving active job, or None if none remains.

    Call this before any operation that would set is_active=True for a job.
    Safe to call repeatedly; always leaves the constraint satisfied.
    """
    if not place_id:
        return None

    all_jobs = (
        db.query(EnrichmentJob)
        .filter(
            EnrichmentJob.place_id == place_id,
            EnrichmentJob.job_type == job_type,
        )
        .order_by(
            EnrichmentJob.priority.desc(),
            EnrichmentJob.created_at.desc(),
        )
        .all()
    )

    active = [j for j in all_jobs if j.is_active]
    inactive = [j for j in all_jobs if not j.is_active]

    # ── Deactivate surplus active rows (keep the first = highest priority/newest) ──
    if len(active) > 1:
        keeper = active[0]
        for extra in active[1:]:
            try:
                extra.is_active = False
                logger.warning(
                    "ensure_single_active_job: deactivated duplicate active job "
                    "id=%s place_id=%s job_type=%s",
                    extra.id, place_id, job_type,
                )
            except Exception as exc:
                logger.error("ensure_single_active_job: deactivate failed id=%s error=%s", extra.id, exc)
        try:
            db.flush()
        except Exception as exc:
            db.rollback()
            logger.error("ensure_single_active_job: flush failed place_id=%s error=%s", place_id, exc)
            return None
        active = [keeper]

    # ── Delete surplus inactive rows (constraint allows only one is_active=False) ──
    if len(inactive) > 1:
        keep_inactive = inactive[0]  # newest (ordered by created_at desc)
        for stale in inactive[1:]:
            try:
                db.delete(stale)
            except Exception as exc:
                logger.error("ensure_single_active_job: delete stale failed id=%s error=%s", stale.id, exc)
        try:
            db.flush()
        except Exception as exc:
            db.rollback()
            logger.error("ensure_single_active_job: flush stale delete failed place_id=%s error=%s", place_id, exc)

    return active[0] if active else None


def schedule_menu_jobs(
    db: Session,
    places: Iterable[Place],
    priority: int = 1,
) -> List[EnrichmentJob]:
    """
    Create pending menu enrichment jobs for places that do not already
    have an active menu job.

    A place is considered already scheduled when an active menu job exists
    with status in:
    - pending
    - running
    """

    place_list = [place for place in places if getattr(place, "id", None)]
    if not place_list:
        return []

    place_ids = [place.id for place in place_list]

    existing_jobs = (
        db.query(EnrichmentJob)
        .filter(
            EnrichmentJob.place_id.in_(place_ids),
            EnrichmentJob.job_type == "menu",
            EnrichmentJob.is_active.is_(True),
            EnrichmentJob.status.in_(ACTIVE_MENU_JOB_STATUSES),
        )
        .all()
    )

    existing_place_ids = {job.place_id for job in existing_jobs if job.place_id}
    created_jobs: List[EnrichmentJob] = []

    for place in place_list:
        if place.id in existing_place_ids:
            continue

        job = EnrichmentJob(
            place_id=place.id,
            job_type="menu",
            priority=priority,
            status="pending",
            is_active=True,
        )
        db.add(job)
        created_jobs.append(job)

        # Protect against duplicate Place objects in the same incoming batch.
        existing_place_ids.add(place.id)

    if not created_jobs:
        return []

    db.commit()

    for job in created_jobs:
        db.refresh(job)

    return created_jobs


def enqueue_menu_job(
    db: Session,
    place_id: str,
    priority: int = HIGH_PRIORITY,
) -> Optional[EnrichmentJob]:
    """
    Manually enqueue a high-priority menu job for a specific place.

    - If an active job (pending/running) already exists: bump priority and return it.
    - Calls ensure_single_active_job first to guarantee constraint safety.
    - Never creates a duplicate is_active=True row.
    """
    if not place_id:
        return None

    # Ensure constraint-safe state before any insert/update
    existing_active = ensure_single_active_job(db, place_id, job_type="menu")

    if existing_active is not None:
        if existing_active.status in ACTIVE_MENU_JOB_STATUSES:
            # Already queued or running — bump priority if lower
            if existing_active.priority < priority:
                existing_active.priority = priority
                try:
                    db.commit()
                except Exception as exc:
                    db.rollback()
                    logger.error("enqueue_menu_job: priority bump commit failed place_id=%s error=%s", place_id, exc)
            return existing_active

        # Active job exists but has unexpected status — deactivate it
        try:
            existing_active.is_active = False
            db.flush()
        except Exception as exc:
            db.rollback()
            logger.error("enqueue_menu_job: deactivate stale job failed place_id=%s error=%s", place_id, exc)
            return None

    job = EnrichmentJob(
        place_id=place_id,
        job_type="menu",
        priority=priority,
        status="pending",
        is_active=True,
    )
    db.add(job)
    try:
        db.commit()
        db.refresh(job)
    except Exception as exc:
        db.rollback()
        logger.error(
            "enqueue_menu_job: insert failed place_id=%s error=%s — possible duplicate",
            place_id, exc,
        )
        return None
    return job