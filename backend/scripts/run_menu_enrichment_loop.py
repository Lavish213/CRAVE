from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func

from app.db.models.enrichment_job import EnrichmentJob
from app.db.models.place import Place
from app.db.session import SessionLocal
from app.services.menu.orchestration.menu_enrichment_selector import (
    get_places_needing_menus,
)
from app.services.menu.orchestration.menu_enrichment_worker import (
    process_menu_job,
)
from app.services.menu.orchestration.menu_job_scheduler import (
    schedule_menu_jobs,
)


SLEEP_SECONDS = 10
SELECT_BATCH_SIZE = 25
JOB_BATCH_SIZE = 10

LOCK_TIMEOUT_SECONDS = 120
RETRY_DELAY_SECONDS = 30
MAX_ATTEMPTS = 3

WORKER_NAME = "menu-loop"


def utcnow() -> datetime:
    return datetime.now(UTC)


def log(message: str) -> None:
    print(f"[{utcnow().isoformat()}] {message}", flush=True)


def error_file(exc: Exception) -> str:
    tb = exc.__traceback__
    if tb is None:
        return "unknown"

    last_tb = tb
    while last_tb.tb_next is not None:
        last_tb = last_tb.tb_next

    return Path(last_tb.tb_frame.f_code.co_filename).name


def state_snapshot(db) -> str:
    pending = (
        db.query(func.count(EnrichmentJob.id))
        .filter(
            EnrichmentJob.status == "pending",
            EnrichmentJob.is_active.is_(True),
        )
        .scalar()
        or 0
    )

    running = (
        db.query(func.count(EnrichmentJob.id))
        .filter(
            EnrichmentJob.status == "running",
            EnrichmentJob.is_active.is_(True),
        )
        .scalar()
        or 0
    )

    failed = (
        db.query(func.count(EnrichmentJob.id))
        .filter(EnrichmentJob.status == "failed")
        .scalar()
        or 0
    )

    completed = (
        db.query(func.count(EnrichmentJob.id))
        .filter(EnrichmentJob.status == "completed")
        .scalar()
        or 0
    )

    total_places = db.query(func.count(Place.id)).scalar() or 0
    with_menu = (
        db.query(func.count(Place.id))
        .filter(Place.has_menu.is_(True))
        .scalar()
        or 0
    )

    return (
        f"state places={total_places} with_menu={with_menu} "
        f"pending={pending} running={running} failed={failed} completed={completed}"
    )


def recover_stuck_jobs(db, now: datetime) -> int:
    recovered = (
        db.query(EnrichmentJob)
        .filter(
            EnrichmentJob.status == "running",
            EnrichmentJob.is_active.is_(True),
            EnrichmentJob.locked_at.is_not(None),
            EnrichmentJob.locked_at < now - timedelta(seconds=LOCK_TIMEOUT_SECONDS),
        )
        .update(
            {
                EnrichmentJob.status: "pending",
                EnrichmentJob.locked_at: None,
                EnrichmentJob.locked_by: None,
                EnrichmentJob.updated_at: now,
                EnrichmentJob.next_run_at: now,
            },
            synchronize_session=False,
        )
    )

    db.commit()
    return int(recovered or 0)


def lock_pending_jobs(db, now: datetime, limit: int) -> list[str]:
    jobs = (
        db.query(EnrichmentJob)
        .filter(
            EnrichmentJob.status == "pending",
            EnrichmentJob.is_active.is_(True),
            EnrichmentJob.next_run_at <= now,
        )
        .order_by(
            EnrichmentJob.priority.desc(),
            EnrichmentJob.created_at.asc(),
            EnrichmentJob.id.asc(),
        )
        .limit(limit)
        .all()
    )

    locked_ids: list[str] = []

    for job in jobs:
        job.status = "running"
        job.locked_at = now
        job.locked_by = WORKER_NAME
        job.attempts = int(job.attempts or 0) + 1
        job.last_attempted_at = now
        job.updated_at = now
        locked_ids.append(job.id)

    db.commit()
    return locked_ids


def apply_retry_or_finalize(job_id: str, exc: Exception) -> None:
    db = SessionLocal()

    try:
        db.rollback()

        job = db.get(EnrichmentJob, job_id)
        if job is None:
            log(f"job_error id={job_id} file={error_file(exc)} error={exc}")
            return

        now = utcnow()

        job.last_error = str(exc)
        job.locked_at = None
        job.locked_by = None
        job.updated_at = now

        if job.status == "failed" and job.is_active is False:
            db.commit()
            log(
                f"job_failed id={job.id} place_id={job.place_id} "
                f"file={error_file(exc)} error={job.last_error}"
            )
            return

        if int(job.attempts or 0) >= MAX_ATTEMPTS:
            job.status = "failed"
            job.is_active = False
            job.completed_at = now
            db.commit()
            log(
                f"job_failed id={job.id} place_id={job.place_id} "
                f"file={error_file(exc)} error={job.last_error}"
            )
            return

        job.status = "pending"
        job.next_run_at = now + timedelta(seconds=RETRY_DELAY_SECONDS)
        db.commit()

        log(
            f"job_retry id={job.id} place_id={job.place_id} "
            f"attempts={job.attempts}/{MAX_ATTEMPTS} "
            f"file={error_file(exc)} error={job.last_error}"
        )

    except Exception as retry_exc:
        db.rollback()
        log(
            f"job_retry_handler_error id={job_id} "
            f"file={error_file(retry_exc)} error={retry_exc}"
        )
    finally:
        db.close()


def run() -> None:
    log("menu enrichment loop started")

    while True:
        locked_job_ids: list[str] = []

        db = SessionLocal()

        try:
            now = utcnow()

            recovered = recover_stuck_jobs(db, now)
            if recovered:
                log(f"recovered_stuck_jobs count={recovered}")

            log(state_snapshot(db))

            places = get_places_needing_menus(
                db=db,
                limit=SELECT_BATCH_SIZE,
            )

            if places:
                log(f"places_needing_menus count={len(places)}")

                created_jobs = schedule_menu_jobs(
                    db=db,
                    places=places,
                )

                if created_jobs:
                    log(f"jobs_scheduled count={len(created_jobs)}")

            locked_job_ids = lock_pending_jobs(
                db=db,
                now=now,
                limit=JOB_BATCH_SIZE,
            )

            if locked_job_ids:
                log(f"jobs_locked count={len(locked_job_ids)} ids={locked_job_ids}")

        except Exception as exc:
            db.rollback()
            log(f"loop_error file={error_file(exc)} error={exc}")

        finally:
            db.close()

        for job_id in locked_job_ids:
            job_db = SessionLocal()

            try:
                job = job_db.get(EnrichmentJob, job_id)
                if job is None:
                    log(f"job_missing id={job_id}")
                    continue

                process_menu_job(job_db, job)

                job_db.expire_all()
                fresh_job = job_db.get(EnrichmentJob, job_id)

                if fresh_job is None:
                    log(f"job_disappeared id={job_id}")
                    continue

                log(
                    f"job_done id={fresh_job.id} place_id={fresh_job.place_id} "
                    f"status={fresh_job.status} attempts={fresh_job.attempts}"
                )

            except Exception as exc:
                job_db.rollback()
                apply_retry_or_finalize(job_id, exc)

            finally:
                job_db.close()

        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    run()