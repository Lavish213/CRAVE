"""
Manual, one-shot verification that SENTRY_DSN is actually wired end-to-end
in whatever environment this is running in. Confirming the env var is *set*
isn't the same as confirming Sentry actually receives events from it — this
endpoint deliberately raises so app/main.py's global_exception_handler runs
for real and calls sentry_sdk.capture_exception, then you check the Sentry
project dashboard for the event.

Gated behind require_api_key (same mechanism every other write/admin-ish
endpoint uses) since it's a deliberate 500 — not something that should be
free for anyone to hit repeatedly.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import require_api_key
from app.db.session import get_db

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/sentry-test", dependencies=[Depends(require_api_key)])
def sentry_test() -> None:
    raise RuntimeError(
        "CRAVE debug/sentry-test: deliberate test error, safe to ignore — "
        "confirms this event reached Sentry."
    )


# backend/GIT_COMMIT.txt -- four levels up from this file
# (routes -> v1 -> api -> app -> backend). Not committed (see .gitignore);
# regenerated fresh right before each deploy. This is the primary source
# for /version: confirmed live that `railway up` (uploading a local
# directory, not a GitHub-connected clone) sets neither
# RAILWAY_GIT_COMMIT_SHA nor an in-container .git directory, so both of
# those were dead ends for this project's actual deploy method.
_GIT_COMMIT_FILE = Path(__file__).resolve().parents[4] / "GIT_COMMIT.txt"


def _git_commit_from_file() -> str | None:
    try:
        return _GIT_COMMIT_FILE.read_text().strip() or None
    except Exception:
        return None


def _git_commit_fallback() -> str | None:
    # Last resort for a plain local run where .git genuinely is present
    # (e.g. `uvicorn app.main:app` from a dev checkout) -- not expected
    # to resolve anything in the deployed container, see above.
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
            .decode()
            .strip()
        )
    except Exception:
        return None


@router.get("/version")
def version() -> dict:
    """
    Answers one question directly, instead of asking someone to trust an
    assurance: "is the commit I think is deployed actually the commit
    that's running?" Reads backend/GIT_COMMIT.txt (written by
    `git rev-parse HEAD > backend/GIT_COMMIT.txt` right before deploying
    -- see the project's deploy instructions) first, since this
    project's actual deploy method (`railway up` from a local checkout)
    doesn't populate RAILWAY_GIT_COMMIT_SHA or carry .git into the
    container -- both kept as fallbacks in case the deploy method ever
    changes to a GitHub-connected one.
    """
    commit = (
        _git_commit_from_file()
        or os.environ.get("RAILWAY_GIT_COMMIT_SHA")
        or _git_commit_fallback()
    )
    return {
        "commit": commit,
        "commit_short": commit[:12] if commit else None,
        "railway_environment": os.environ.get("RAILWAY_ENVIRONMENT_NAME")
        or os.environ.get("RAILWAY_ENVIRONMENT"),
        "railway_deployment_id": os.environ.get("RAILWAY_DEPLOYMENT_ID"),
    }


@router.get("/scheduler", dependencies=[Depends(require_api_key)])
def scheduler_diagnostics(db: Session = Depends(get_db)) -> dict:
    """
    Answers "is a background job the reason requests are slow right now?"
    directly from data, instead of guessing.

    app/main.py's lifespan starts app/scheduler.py's BackgroundScheduler
    in-process (settings.run_embedded_scheduler, default True) unless
    RUN_EMBEDDED_SCHEDULER=false is set on this service AND a separate
    `python -m app.scheduler_worker` process is running the same jobs
    instead (see that module's docstring). When it runs embedded, its
    APScheduler job threads share this process's GIL and DB connection
    pool with every HTTP request thread — a CPU/IO-heavy job (image
    resize/hash, HTML parsing, external API calls) can starve request
    handling for its own run duration. This was already confirmed live
    once (a menu_enrichment run overlapping image_ingestion caused
    request timeouts unrelated to client network quality — see
    settings.py's run_embedded_scheduler comment).

    job_runs rows (written by app.core.job_run_tracker.track_job_run,
    wrapping every job body in app/scheduler.py) let us check directly
    whether a job was running during a specific slow request: compare its
    started_at/finished_at window against the request's timestamp.
    """
    from app.config.settings import settings
    from app.db.models.job_run import JobRun

    recent_runs = []
    try:
        rows = (
            db.execute(
                select(JobRun).order_by(JobRun.started_at.desc()).limit(25)
            )
            .scalars()
            .all()
        )
        for r in rows:
            duration_seconds: Optional[float] = None
            if r.finished_at is not None:
                duration_seconds = (r.finished_at - r.started_at).total_seconds()
            recent_runs.append(
                {
                    "job_name": r.job_name,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                    "duration_seconds": duration_seconds,
                    # still-running (or crashed without reaching the tracker's
                    # finally block) if finished_at never got set
                    "still_running_or_crashed": r.finished_at is None,
                    "success": r.success,
                    "summary": r.summary,
                }
            )
    except Exception as exc:
        return {
            "run_embedded_scheduler": settings.run_embedded_scheduler,
            "job_runs_query_failed": str(exc),
            "recent_runs": [],
        }

    return {
        "run_embedded_scheduler": settings.run_embedded_scheduler,
        "recent_runs": recent_runs,
    }


@router.get("/map-query-plan", dependencies=[Depends(require_api_key)])
def map_query_plan(
    lat: float,
    lng: float,
    radius_km: float = 5.0,
    limit: int = 250,
    db: Session = Depends(get_db),
) -> dict:
    """
    Answers "is the map bounding-box query itself slow, and why?" with real
    EXPLAIN ANALYZE output, instead of guessing further. Built after ruling
    out both the embedded scheduler (split into its own service, latency
    unchanged) and Redis (REDIS_URL unset, never even attempted) as the
    cause of the map/geojson endpoint's ~60-67s stalls -- the app's own
    request logs show the entire delay happens inside the DB query itself,
    before fetch_places_for_map_geojson even returns.

    No-ops safely (returns an error string, not a 500) on SQLite/local dev,
    since EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) is Postgres-only syntax.
    """
    from sqlalchemy import text
    from app.services.geo.bounding_box import bounding_box

    if not str(db.bind.url).startswith("postgresql"):
        return {"error": "map-query-plan is Postgres-only; this DB is not Postgres"}

    bb = bounding_box(lat, lng, radius_km)

    counts = {}
    try:
        counts["place_total"] = db.execute(text("SELECT count(*) FROM place")).scalar()
        counts["place_active"] = db.execute(
            text("SELECT count(*) FROM place WHERE is_active = true")
        ).scalar()
        counts["place_active_in_bbox"] = db.execute(
            text(
                "SELECT count(*) FROM place WHERE is_active = true "
                "AND lat IS NOT NULL AND lng IS NOT NULL "
                "AND lat >= :min_lat AND lat <= :max_lat "
                "AND lng >= :min_lng AND lng <= :max_lng"
            ),
            {
                "min_lat": bb.min_lat, "max_lat": bb.max_lat,
                "min_lng": bb.min_lng, "max_lng": bb.max_lng,
            },
        ).scalar()
    except Exception as exc:
        counts["error"] = str(exc)

    explain_query = text(
        "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) "
        "SELECT DISTINCT id, name, lat, lng, city_id, price_tier, rank_score, has_menu "
        "FROM place "
        "WHERE is_active = true "
        "AND lat IS NOT NULL AND lng IS NOT NULL "
        "AND lat >= :min_lat AND lat <= :max_lat "
        "AND lng >= :min_lng AND lng <= :max_lng "
        "ORDER BY rank_score DESC, id ASC "
        "LIMIT :limit"
    )

    plan = None
    plan_error = None
    try:
        row = db.execute(
            explain_query,
            {
                "min_lat": bb.min_lat, "max_lat": bb.max_lat,
                "min_lng": bb.min_lng, "max_lng": bb.max_lng,
                "limit": limit,
            },
        ).scalar()
        plan = row
    except Exception as exc:
        plan_error = str(exc)

    return {
        "bounding_box": {
            "min_lat": bb.min_lat, "max_lat": bb.max_lat,
            "min_lng": bb.min_lng, "max_lng": bb.max_lng,
        },
        "counts": counts,
        "explain_plan": plan,
        "explain_plan_error": plan_error,
    }
