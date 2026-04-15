"""
Background scheduler for CRAVE pipeline automation.

Uses APScheduler's BackgroundScheduler (thread-based) so it is compatible
with the synchronous SQLAlchemy sessions used by all existing workers.

Each job creates and closes its own DB session — sessions are never shared
across threads or job invocations.  All jobs are fire-and-forget: exceptions
are logged but never re-raised, so a single job failure cannot kill the
scheduler or any other job.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Job implementations
# ---------------------------------------------------------------------------

def _job_discovery() -> None:
    """Discovery cycle: fetch + promote candidates into places."""
    from contextlib import suppress
    from app.db.session import SessionLocal
    from app.services.discovery.pipeline_v2 import run_discovery_pipeline_v2

    db = SessionLocal()
    try:
        result = run_discovery_pipeline_v2(db=db, limit=50)
        logger.info("scheduler_discovery_complete promoted=%s", result.get("promoted", 0))
    except Exception as exc:
        logger.exception("scheduler_discovery_failed error=%s", exc)
        with suppress(Exception):
            db.rollback()
    finally:
        with suppress(Exception):
            db.close()


def _job_menu_enrichment() -> None:
    """Menu enrichment: ingest menu signals for known places."""
    # run_menu_worker() (MenuWorker.run) manages its own DB session lifecycle
    # internally — it opens a SessionLocal() per batch iteration and closes it
    # in a try/finally block, so no explicit session management is needed here.
    from app.services.workers.menu_worker import run_menu_worker

    try:
        run_menu_worker()
        logger.info("scheduler_menu_complete")
    except Exception as exc:
        logger.exception("scheduler_menu_failed error=%s", exc)


def _job_score_recompute() -> None:
    """Score recompute: recalculate rank_score for unscored / stale places."""
    from contextlib import suppress
    from app.db.session import SessionLocal
    from app.db.models.place import Place
    from app.services.scoring.recompute import recompute_place_scores
    from sqlalchemy import or_

    db = SessionLocal()
    try:
        places = (
            db.query(Place)
            .filter(Place.is_active.is_(True))
            .filter(
                or_(Place.rank_score == 0, Place.last_scored_at.is_(None))
            )
            .limit(500)
            .all()
        )
        if places:
            updated = recompute_place_scores(db, places=places)
            db.commit()
            logger.info("scheduler_recompute_complete updated=%s", updated)
        else:
            logger.debug("scheduler_recompute_noop no_stale_places")
    except Exception as exc:
        logger.exception("scheduler_recompute_failed error=%s", exc)
        with suppress(Exception):
            db.rollback()
    finally:
        with suppress(Exception):
            db.close()


def _job_ranking_update() -> None:
    """Ranking update: recompute city-level place rankings."""
    from contextlib import suppress
    from app.db.session import SessionLocal
    from app.workers.ranking_worker import run_ranking_cycle

    db = SessionLocal()
    try:
        run_ranking_cycle(db)
        logger.info("scheduler_ranking_complete")
    except Exception as exc:
        logger.exception("scheduler_ranking_failed error=%s", exc)
        with suppress(Exception):
            db.rollback()
    finally:
        with suppress(Exception):
            db.close()


def _job_share_parser() -> None:
    """Share parser: process pending CraveItem share URLs."""
    try:
        from app.workers.share_parser_worker import run_share_parser
        result = run_share_parser()  # opens/closes its own session when db=None
        if result["processed"]:
            logger.info(
                "scheduler_share_parser_complete processed=%s matched=%s unmatched=%s error=%s",
                result["processed"],
                result["matched"],
                result["unmatched"],
                result["error"],
            )
        else:
            logger.debug("scheduler_share_parser_noop no_pending_items")
    except Exception as exc:
        logger.exception("scheduler_share_parser_failed error=%s", exc)


# ---------------------------------------------------------------------------
# Scheduler factory
# ---------------------------------------------------------------------------

def create_scheduler() -> BackgroundScheduler:
    """
    Build and return a configured BackgroundScheduler.

    The scheduler is NOT started here — call .start() in the FastAPI lifespan
    so it only runs when the application is fully initialised.
    """
    scheduler = BackgroundScheduler(
        job_defaults={
            "coalesce": True,       # merge missed runs into a single run
            "max_instances": 1,     # never overlap two instances of the same job
            "misfire_grace_time": 60,  # tolerate up to 60 s of startup delay
        }
    )

    # discovery cycle — every 5 minutes
    scheduler.add_job(
        _job_discovery,
        trigger="interval",
        minutes=5,
        id="discovery",
        name="CRAVE discovery cycle",
    )

    # menu enrichment — every 10 minutes
    scheduler.add_job(
        _job_menu_enrichment,
        trigger="interval",
        minutes=10,
        id="menu_enrichment",
        name="CRAVE menu enrichment",
    )

    # score recompute — every 15 minutes
    scheduler.add_job(
        _job_score_recompute,
        trigger="interval",
        minutes=15,
        id="score_recompute",
        name="CRAVE score recompute",
    )

    # ranking update — every 30 minutes
    scheduler.add_job(
        _job_ranking_update,
        trigger="interval",
        minutes=30,
        id="ranking_update",
        name="CRAVE ranking update",
    )

    # share parser — every 2 minutes
    scheduler.add_job(
        _job_share_parser,
        trigger="interval",
        minutes=2,
        id="share_parser",
        name="CRAVE share parser",
    )

    return scheduler
