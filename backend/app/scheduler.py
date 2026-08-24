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
    from app.core.job_run_tracker import track_job_run

    db = SessionLocal()
    try:
        with track_job_run("discovery") as run:
            result = run_discovery_pipeline_v2(db=db, limit=50)
            promoted = result.get("promoted", 0)
            logger.info("scheduler_discovery_complete promoted=%s", promoted)
            run.set_summary(f"promoted={promoted}")
    except Exception as exc:
        logger.exception("scheduler_discovery_failed error=%s", exc)
        with suppress(Exception):
            db.rollback()
    finally:
        with suppress(Exception):
            db.close()


def _job_video_processing() -> None:
    """
    Video processing: picks up 'queued' (client-confirmed uploads) and any
    stale 'processing' rows (a previous run crashed mid-item -- see
    video_processing_worker.py's own docstring for why that's a safe,
    self-healing recovery here and not the bug class it was in the
    Node.js reference this was ported from), then runs each through
    download -> ffprobe -> ffmpeg compress -> food-score -> thumbnail ->
    approve/reject. Deliberately its own scheduler job (not a FastAPI
    BackgroundTask off the confirm-upload route, unlike photos) -- ffmpeg
    + ML inference are real CPU work, and this is exactly the kind of
    work app/scheduler_worker.py's own split exists to keep off the
    process serving live requests.
    """
    from contextlib import suppress
    from app.db.session import SessionLocal
    from app.services.video.video_processing_worker import process_pending_videos
    from app.core.job_run_tracker import track_job_run

    db = SessionLocal()
    try:
        with track_job_run("video_processing") as run:
            result = process_pending_videos(db, limit=20)
            logger.info("scheduler_video_processing_complete %s", result)
            run.set_summary(str(result)[:500])
    except Exception as exc:
        logger.exception("scheduler_video_processing_failed error=%s", exc)
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
    from app.core.job_run_tracker import track_job_run

    try:
        with track_job_run("menu_enrichment") as run:
            run_menu_worker()
            logger.info("scheduler_menu_complete")
            run.set_summary("completed")
    except Exception as exc:
        logger.exception("scheduler_menu_failed error=%s", exc)


def _job_osm_ingest() -> None:
    """
    OSM acquisition: fetch new candidate restaurants/cafes/bars from the
    free public Overpass API for a rotating slice of active cities.

    This is the acquisition half that was missing — _job_discovery (above)
    only ever promoted candidates already sitting in discovery_candidates;
    nothing scheduled fetched new ones from the outside world. Free/no API
    key, unlike Google Places, so no budget decision is needed to run this
    unattended.
    """
    from contextlib import suppress
    from app.db.session import SessionLocal
    from app.services.discovery.osm_ingest_job import run_osm_city_ingest
    from app.core.job_run_tracker import track_job_run

    db = SessionLocal()
    try:
        with track_job_run("osm_ingest") as run:
            result = run_osm_city_ingest(db=db)
            logger.info("scheduler_osm_ingest_complete %s", result)
            run.set_summary(str(result)[:500])
    except Exception as exc:
        logger.exception("scheduler_osm_ingest_failed error=%s", exc)
        with suppress(Exception):
            db.rollback()
    finally:
        with suppress(Exception):
            db.close()


def _job_overture_ingest() -> None:
    """
    Overture Maps acquisition: same role as _job_osm_ingest above, second
    free source. Reads public Parquet directly off S3 (no API key, no
    per-request billing) via app.services.discovery.overture_places, so like
    OSM it can run unattended with no budget decision.
    """
    from contextlib import suppress
    from app.db.session import SessionLocal
    from app.services.discovery.overture_ingest_job import run_overture_city_ingest
    from app.core.job_run_tracker import track_job_run

    db = SessionLocal()
    try:
        with track_job_run("overture_ingest") as run:
            result = run_overture_city_ingest(db=db)
            logger.info("scheduler_overture_ingest_complete %s", result)
            run.set_summary(str(result)[:500])
    except Exception as exc:
        logger.exception("scheduler_overture_ingest_failed error=%s", exc)
        with suppress(Exception):
            db.rollback()
    finally:
        with suppress(Exception):
            db.close()


def _job_score_recompute() -> None:
    """Score recompute: recalculate rank_score for unscored / stale places."""
    from contextlib import suppress
    from app.db.session import SessionLocal
    from app.db.models.place import Place
    from app.workers.recompute_scores_worker import recompute_places_v4
    from app.core.job_run_tracker import track_job_run
    from sqlalchemy import or_

    from sqlalchemy.orm import selectinload

    db = SessionLocal()
    try:
        with track_job_run("score_recompute") as run:
            # recompute_places_v4 -> _score_batch reads place.city for
            # city-aware scoring weights -- Place.city defaults to lazy
            # loading now (see category.py's comment for why), so this
            # batch fetch needs its own explicit eager-load option to
            # avoid a per-place query for each of up to 500 places, every
            # 15 minutes.
            places = (
                db.query(Place)
                .options(selectinload(Place.city))
                .filter(Place.is_active.is_(True))
                .filter(
                    or_(Place.rank_score == 0, Place.last_scored_at.is_(None))
                )
                .limit(500)
                .all()
            )
            if places:
                # Real v4 scorer (signal decay, image/menu/hitlist/creator/award/
                # blog/risk signals, cache invalidation) — previously this called
                # the Phase-1 placeholder in app/services/scoring/recompute.py,
                # which never read any of that signal data.
                updated = recompute_places_v4(db, places=places)
                db.commit()
                logger.info("scheduler_recompute_complete updated=%s", updated)
                run.set_summary(f"updated={updated}")
            else:
                logger.debug("scheduler_recompute_noop no_stale_places")
                run.set_summary("no_stale_places")
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
    from app.core.job_run_tracker import track_job_run

    db = SessionLocal()
    try:
        with track_job_run("ranking_update") as run:
            run_ranking_cycle(db)
            logger.info("scheduler_ranking_complete")
            run.set_summary("completed")
    except Exception as exc:
        logger.exception("scheduler_ranking_failed error=%s", exc)
        with suppress(Exception):
            db.rollback()
    finally:
        with suppress(Exception):
            db.close()


def _job_image_ingestion() -> None:
    """
    Image ingestion: backfill/refresh place photos via Google Places.

    ImageWorker was fully built (retry-attempt capping, image_blocked after
    repeated failures, invariant repair, primary-image re-election, cache
    invalidation) but was previously only reachable through
    app/workers/master_worker.py — a `while True` process nothing launched.
    This was the entire reason images never refreshed automatically.
    """
    from contextlib import suppress
    from app.db.session import SessionLocal
    from app.workers.image_worker import ImageWorker
    from app.core.job_run_tracker import track_job_run

    db = SessionLocal()
    try:
        with track_job_run("image_ingestion") as run:
            # Bumped from 50 — live-confirmed (a real photo URL returned
            # "Image not found" because Google's photo reference had
            # expired) that the stale-refresh backlog is large enough to
            # visibly affect what users see right now, same as
            # menu_worker's backlog. Still under MAX_BATCH_SIZE (200) and
            # moderate for the same reason as that change: this scheduler
            # runs embedded in the same process serving web requests.
            result = ImageWorker().run(db=db, limit=100)
            logger.info("scheduler_image_ingestion_complete %s", result)
            run.set_summary(str(result)[:500])
    except Exception as exc:
        logger.exception("scheduler_image_ingestion_failed error=%s", exc)
        with suppress(Exception):
            db.rollback()
    finally:
        with suppress(Exception):
            db.close()


def _job_moderation_queue_health_check() -> None:
    """
    Catches a silent deadlock, not a routine failure: review_image/review_queue
    in app/api/v1/routes/moderation.py fail closed on purpose (require_admin
    404s everyone if ADMIN_USER_IDS is unset — "an unset allowlist means
    nobody can review", per that module's own docstring). That's the right
    call for a route, but it means an accidentally-unset/misconfigured env
    var produces no error anywhere — the review queue just silently piles up
    forever with no admin able to drain it, and nothing before this ever
    noticed. logger.error here reaches Sentry automatically the same way any
    other logger.error in this app does (see app/main.py's sentry_sdk.init —
    default_integrations isn't disabled, so its LoggingIntegration turns
    ERROR-level log calls into real Sentry events on its own).
    """
    from contextlib import suppress
    from app.core.job_run_tracker import track_job_run
    from app.db.session import SessionLocal
    from app.db.models.place_image import PlaceImage
    from app.services.images.upload_moderation import MOD_PENDING_REVIEW
    from app.api.v1.routes.moderation import _admin_ids

    db = SessionLocal()
    try:
        with track_job_run("moderation_queue_health_check") as run:
            pending_count = (
                db.query(PlaceImage)
                .filter(PlaceImage.moderation_status == MOD_PENDING_REVIEW)
                .count()
            )

            if pending_count > 0 and not _admin_ids():
                logger.error(
                    "moderation_queue_undrainable pending_count=%s — "
                    "ADMIN_USER_IDS is unset/empty, so nobody can reach "
                    "POST /moderation/images/{id}/review to clear this queue",
                    pending_count,
                )
                run.set_summary(f"UNDRAINABLE pending={pending_count}")
            elif pending_count > 0:
                logger.info("moderation_queue_health pending_count=%s", pending_count)
                run.set_summary(f"pending={pending_count}")
            else:
                run.set_summary("empty")
    except Exception as exc:
        logger.exception("scheduler_moderation_health_check_failed error=%s", exc)
        with suppress(Exception):
            db.rollback()
    finally:
        with suppress(Exception):
            db.close()


def _job_share_parser() -> None:
    """Share parser: process pending CraveItem share URLs."""
    from app.core.job_run_tracker import track_job_run

    try:
        with track_job_run("share_parser") as run:
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
                run.set_summary(
                    f"processed={result['processed']} matched={result['matched']} "
                    f"unmatched={result['unmatched']}"
                )
            else:
                logger.debug("scheduler_share_parser_noop no_pending_items")
                run.set_summary("no_pending_items")
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

    # OSM acquisition — once every 24 hours (rotates through active cities;
    # free public API, gentle cadence matches "don't hammer a free service")
    scheduler.add_job(
        _job_osm_ingest,
        trigger="interval",
        hours=24,
        id="osm_ingest",
        name="CRAVE OSM acquisition",
    )

    # Overture Maps acquisition — once every 24 hours (rotates through
    # active cities same as OSM; free/no API key)
    scheduler.add_job(
        _job_overture_ingest,
        trigger="interval",
        hours=24,
        id="overture_ingest",
        name="CRAVE Overture Maps acquisition",
    )

    # video processing — every 3 minutes. Tighter than most other jobs on
    # purpose: unlike a background enrichment/scoring pass, there's a
    # real person waiting to see their clip go live.
    scheduler.add_job(
        _job_video_processing,
        trigger="interval",
        minutes=3,
        id="video_processing",
        name="CRAVE video processing",
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

    # image ingestion — every 20 minutes
    scheduler.add_job(
        _job_image_ingestion,
        trigger="interval",
        minutes=20,
        id="image_ingestion",
        name="CRAVE image ingestion",
    )

    # moderation queue health check — every 6 hours. Cheap (one COUNT query)
    # and only ever loud when something is actually wrong (see the job's
    # own docstring for what it's guarding against).
    scheduler.add_job(
        _job_moderation_queue_health_check,
        trigger="interval",
        hours=6,
        id="moderation_queue_health_check",
        name="CRAVE moderation queue health check",
    )

    return scheduler
