from __future__ import annotations

from typing import Iterable, List

from sqlalchemy.orm import Session

from app.db.models.enrichment_job import EnrichmentJob
from app.db.models.place import Place


ACTIVE_MENU_JOB_STATUSES = ("pending", "running")


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