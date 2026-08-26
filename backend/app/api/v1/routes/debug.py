"""
Manual, one-shot verification that SENTRY_DSN is actually wired end-to-end
in whatever environment this is running in. Confirming the env var is *set*
isn't the same as confirming Sentry actually receives events from it — this
endpoint deliberately raises so app/main.py's global_exception_handler runs
for real and calls sentry_sdk.capture_exception, then you check the Sentry
project dashboard for the event.

Gated behind require_debug_api_key (a server-only secret, separate from
the app-wide API_KEY -- see that dependency's docstring) since it's a
deliberate 500, not something that should be free for anyone to hit
repeatedly.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import require_debug_api_key
from app.core.rate_limit import rate_limit
from app.db.session import get_db

# rate_limit at the router level (not per-route, since /version
# deliberately carries no auth at all -- see its own docstring) closes a
# real gap: 5 of these 6 endpoints had no rate limit at all, and
# /version had neither guard.
#
# The 6 non-version endpoints require require_debug_api_key (header
# x-debug-api-key, env var DEBUG_API_KEY) rather than the app-wide
# require_api_key. That distinction matters: API_KEY ships inside the
# public app bundle as EXPO_PUBLIC_API_KEY (not a real secret -- anyone
# who extracts it from the client has it), while several of these routes
# run genuine DB work (EXPLAIN ANALYZE in map-query-plan/
# categories-query-plan/map-query-timing) or return raw per-user event
# rows (recommendation-events, scheduler). DEBUG_API_KEY is a
# server-only value set in Railway and never referenced by any
# EXPO_PUBLIC_* var, so it never leaves the server -- see
# require_debug_api_key's docstring in app/core/auth.py.
router = APIRouter(prefix="/debug", tags=["debug"], dependencies=[Depends(rate_limit)])


@router.get("/sentry-test", dependencies=[Depends(require_debug_api_key)])
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


@router.get("/scheduler", dependencies=[Depends(require_debug_api_key)])
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


@router.get("/recommendation-events", dependencies=[Depends(require_debug_api_key)])
def recommendation_events_debug(
    event_type: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db),
) -> dict:
    """
    Read-only window into the Recommendation Ledger for live production
    verification (confirming save/unsave/rank events actually land, and
    that a resubmitted client_event_id dedupes instead of double-counting)
    without needing a Railway console session or direct DB access for
    every check -- this is a plain HTTPS endpoint, reachable the same way
    /version and /scheduler already are.

    `limit` is capped at 100 -- this is a debug aid for eyeballing recent
    rows, not a paginated export.
    """
    from app.db.models.recommendation_event import RecommendationEvent

    limit = max(1, min(limit, 100))

    query = db.query(RecommendationEvent).order_by(RecommendationEvent.created_at.desc())
    if event_type:
        query = query.filter(RecommendationEvent.event_type == event_type)

    rows = query.limit(limit).all()

    return {
        "count": len(rows),
        "events": [
            {
                "id": r.id,
                "event_type": r.event_type,
                "client_event_id": r.client_event_id,
                "place_id": r.place_id,
                "surface": r.surface,
                "position": r.position,
                "rank_percentile": r.rank_percentile,
                "city_id": r.city_id,
                "query": r.query,
                "user_id": r.user_id,
                "session_id": r.session_id,
                # Added for the Craves/Map instrumentation verification pass
                # (2026-08-26) -- without this the debug endpoint couldn't
                # show the one field needed to verify a stable session id
                # across an impression -> selection pair, making that check
                # impossible to actually perform.
                "search_session_id": r.search_session_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.get("/map-query-plan", dependencies=[Depends(require_debug_api_key)])
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
        counts["place_total"] = db.execute(text("SELECT count(*) FROM places")).scalar()
        counts["place_active"] = db.execute(
            text("SELECT count(*) FROM places WHERE is_active = true")
        ).scalar()
        counts["place_active_in_bbox"] = db.execute(
            text(
                "SELECT count(*) FROM places WHERE is_active = true "
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
        # A failed statement leaves the Postgres transaction aborted --
        # every subsequent statement on this connection (the EXPLAIN
        # query below included) would fail with "current transaction is
        # aborted" otherwise, masking the real error.
        db.rollback()
        counts["error"] = str(exc)

    explain_query = text(
        "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) "
        "SELECT DISTINCT id, name, lat, lng, city_id, price_tier, rank_score, has_menu "
        "FROM places "
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
        # Matches the counts block above and categories_query_plan's
        # equivalent block -- a failed statement leaves the transaction
        # aborted for anything else on this connection afterward.
        db.rollback()
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


@router.get("/categories-query-plan", dependencies=[Depends(require_debug_api_key)])
def categories_query_plan(
    lat: float,
    lng: float,
    radius_km: float = 5.0,
    limit: int = 250,
    db: Session = Depends(get_db),
) -> dict:
    """
    map-query-timing isolated the ~60-67s map/geojson delay to
    get_categories_for_places_bulk specifically -- the base place query
    and the images bulk lookup are both fast (sub-second) against the
    same 250 place IDs. This runs EXPLAIN ANALYZE against that exact
    query, plus a raw row count of place_categories, to see whether it's
    an unused index or a bloated table (the same "unbounded growth"
    shape already found once this session in place_images).
    """
    from sqlalchemy import text
    from app.services.geo.bounding_box import bounding_box
    from app.db.models.place import Place

    if not str(db.bind.url).startswith("postgresql"):
        return {"error": "categories-query-plan is Postgres-only; this DB is not Postgres"}

    bb = bounding_box(lat, lng, radius_km)

    place_ids = [
        r.id
        for r in db.query(Place.id, Place.rank_score)
        .filter(
            Place.is_active.is_(True),
            Place.lat.isnot(None),
            Place.lng.isnot(None),
            Place.lat >= bb.min_lat,
            Place.lat <= bb.max_lat,
            Place.lng >= bb.min_lng,
            Place.lng <= bb.max_lng,
        )
        .distinct()
        .order_by(Place.rank_score.desc(), Place.id.asc())
        .limit(limit)
        .all()
    ]

    counts = {}
    try:
        counts["place_categories_total"] = db.execute(
            text("SELECT count(*) FROM place_categories")
        ).scalar()
        counts["place_images_total"] = db.execute(
            text("SELECT count(*) FROM place_images")
        ).scalar()
    except Exception as exc:
        db.rollback()
        counts["error"] = str(exc)

    if not place_ids:
        return {"counts": counts, "explain_plan": None, "explain_plan_error": "no place_ids in bbox"}

    placeholders = ", ".join(f":pid{i}" for i in range(len(place_ids)))
    params = {f"pid{i}": pid for i, pid in enumerate(place_ids)}

    explain_query = text(
        "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) "
        "SELECT place_categories.place_id, categories.* "
        "FROM place_categories "
        "JOIN categories ON place_categories.category_id = categories.id "
        f"WHERE place_categories.place_id IN ({placeholders}) "
        "ORDER BY place_categories.place_id ASC, categories.name ASC, categories.id ASC"
    )

    plan = None
    plan_error = None
    try:
        plan = db.execute(explain_query, params).scalar()
    except Exception as exc:
        db.rollback()
        plan_error = str(exc)

    return {
        "place_ids_count": len(place_ids),
        "counts": counts,
        "explain_plan": plan,
        "explain_plan_error": plan_error,
    }


@router.get("/map-query-timing", dependencies=[Depends(require_debug_api_key)])
def map_query_timing(
    lat: float,
    lng: float,
    radius_km: float = 5.0,
    limit: int = 250,
    city_id: Optional[str] = None,
    category_id: Optional[str] = None,
    db: Session = Depends(get_db),
) -> dict:
    """
    map-query-plan proved the base place-selection query itself is fast
    (4.45ms EXPLAIN ANALYZE execution time against 33k places) -- so the
    ~60-67s the live /map/geojson endpoint spends has to be in one of the
    two steps that run *after* that query inside fetch_places_for_map:
    the bulk category lookup and the bulk primary-image lookup for the
    resulting place IDs. Neither was measured independently until now.

    Calls the exact same production functions (not a re-implementation)
    with a timer around each phase, so this reflects reality rather than
    a plausible-looking approximation.
    """
    import time

    from app.services.geo.bounding_box import bounding_box
    from app.db.models.place import Place
    from app.db.models.place_categories import place_categories
    from app.services.query.place_image_visibility_query import get_primary_image_urls_bulk
    from app.services.query.place_category_query import get_categories_for_places_bulk

    bb = bounding_box(lat, lng, radius_km)

    t0 = time.perf_counter()

    # Postgres requires every SELECT DISTINCT query's ORDER BY expressions to
    # appear in the select list -- rank_score has to be selected here even
    # though only .id is used below, to match Postgres's own requirement
    # (this is the exact error the production query avoids by selecting
    # rank_score as one of its real output columns).
    q = db.query(Place.id, Place.rank_score).filter(
        Place.is_active.is_(True),
        Place.lat.isnot(None),
        Place.lng.isnot(None),
        Place.lat >= bb.min_lat,
        Place.lat <= bb.max_lat,
        Place.lng >= bb.min_lng,
        Place.lng <= bb.max_lng,
    )
    if city_id:
        q = q.filter(Place.city_id == city_id)
    if category_id:
        q = q.join(
            place_categories, place_categories.c.place_id == Place.id
        ).filter(place_categories.c.category_id == category_id)

    place_ids = [
        r.id
        for r in q.distinct()
        .order_by(Place.rank_score.desc(), Place.id.asc())
        .limit(limit)
        .all()
    ]

    t1 = time.perf_counter()

    category_error = None
    try:
        category_map = get_categories_for_places_bulk(db, place_ids=place_ids)
    except Exception as exc:
        category_map = {}
        category_error = str(exc)

    t2 = time.perf_counter()

    image_error = None
    try:
        image_map = get_primary_image_urls_bulk(db, place_ids=place_ids)
    except Exception as exc:
        image_map = {}
        image_error = str(exc)

    t3 = time.perf_counter()

    return {
        "place_ids_count": len(place_ids),
        "base_query_seconds": round(t1 - t0, 4),
        "categories_bulk_seconds": round(t2 - t1, 4),
        "categories_bulk_error": category_error,
        "categories_matched": len(category_map),
        "images_bulk_seconds": round(t3 - t2, 4),
        "images_bulk_error": image_error,
        "images_matched": len(image_map),
        "total_seconds": round(t3 - t0, 4),
    }
