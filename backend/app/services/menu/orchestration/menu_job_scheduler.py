from __future__ import annotations

from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from app.db.models.enrichment_job import EnrichmentJob
from app.db.models.place import Place


ACTIVE_MENU_JOB_STATUSES = ("pending", "running")

HIGH_PRIORITY = 10
NORMAL_PRIORITY = 1


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

    If an active job (pending/running) already exists, returns None (skip).
    If a stale active job exists (stuck), deactivates it and creates a new one.
    """
    if not place_id:
        return None

    existing = (
        db.query(EnrichmentJob)
        .filter(
            EnrichmentJob.place_id == place_id,
            EnrichmentJob.job_type == "menu",
            EnrichmentJob.is_active.is_(True),
        )
        .first()
    )

    if existing is not None:
        if existing.status in ACTIVE_MENU_JOB_STATUSES:
            # Already queued or running — bump priority if lower
            if existing.priority < priority:
                existing.priority = priority
                db.commit()
            return existing

        # Stale active job (shouldn't happen, but deactivate it)
        existing.is_active = False
        db.flush()

    job = EnrichmentJob(
        place_id=place_id,
        job_type="menu",
        priority=priority,
        status="pending",
        is_active=True,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job