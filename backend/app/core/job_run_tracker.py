"""
Minimal job-run observability for the APScheduler jobs in app/scheduler.py.

Before this existed, every scheduled job logged one line to stdout on
success or failure and nothing else — there was no queryable record of
what ran, when, or what it did. That absence is a real part of how a
two-month production outage went unnoticed: even a running app gave no
"is the pipeline actually doing anything" signal short of grepping logs.

Usage:
    from app.core.job_run_tracker import track_job_run

    def _job_something() -> None:
        with track_job_run("something") as run:
            ... do the work ...
            run.set_summary(f"processed={n}")

On success, writes a JobRun row with success=True and the summary you set.
On exception, writes success=False with the traceback, THEN RE-RAISES —
this tracker only observes, it never changes a job's error handling.
"""
from __future__ import annotations

import logging
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.db.models.job_run import JobRun

logger = logging.getLogger(__name__)


class JobRunHandle:
    def __init__(self) -> None:
        self._summary: str | None = None

    def set_summary(self, summary: str) -> None:
        self._summary = summary[:500] if summary else None


@contextmanager
def track_job_run(job_name: str):
    """
    Wraps a scheduled job body. Uses its own dedicated DB session for
    bookkeeping only — never shared with the job's own session(s) — and
    never lets a bookkeeping failure (e.g. a DB hiccup) take down the job
    itself or mask the job's real exception.
    """
    handle = JobRunHandle()
    db = SessionLocal()
    run = JobRun(job_name=job_name)

    try:
        db.add(run)
        db.commit()
    except Exception:
        logger.debug("job_run_tracker_start_failed job=%s", job_name, exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass

    try:
        yield handle
        run.success = True
    except Exception as exc:
        run.success = False
        run.error = traceback.format_exc()[-4000:]
        try:
            from app.config.settings import settings
            if settings.sentry_dsn:
                import sentry_sdk
                sentry_sdk.capture_exception(exc)
        except Exception:
            pass
        raise
    finally:
        run.finished_at = datetime.now(timezone.utc)
        run.summary = handle._summary
        try:
            db.commit()
        except Exception:
            logger.debug(
                "job_run_tracker_finish_failed job=%s", job_name, exc_info=True
            )
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            db.close()
