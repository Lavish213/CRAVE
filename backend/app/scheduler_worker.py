"""
Standalone process for the CRAVE background job scheduler.

Split out from app/main.py's lifespan (see settings.run_embedded_scheduler's
docstring for the full reasoning): APScheduler's BackgroundScheduler runs
jobs in threads inside whichever process starts it. When that process also
serves HTTP requests — the default, single-uvicorn-worker setup this app
runs in prod (see railway.toml's startCommand) — CPU-bound job work (image
resize/hash, HTML parsing, OCR) competes with the GIL for time the
request-handling event loop needs, causing request timeouts unrelated to
client network quality. Confirmed in production: a single menu_enrichment
run took 3h21m end to end while image_ingestion ran every 20 minutes
concurrently, both in the same process already serving map/feed requests.

Deploy this as its own Railway service:
    Start command: cd backend && python -m app.scheduler_worker
    (needs the same DATABASE_URL, GOOGLE_PLACES_API_KEY, R2_*, SUPABASE_*,
    etc. env vars as the web service — it runs the identical jobs, just in
    its own process, so no DB migration step is needed here since the web
    service's startCommand already runs `alembic upgrade head`.)

The standalone process is default-off even after deployment. Set
SCHEDULER_WORKER_ENABLED=true together with an explicit comma-separated
SCHEDULER_JOB_ALLOWLIST. An enabled worker with an empty/unknown allowlist
fails closed. See docs/SCHEDULER_WORKER_ROLLOUT.md for the phased rollout.

Then set RUN_EMBEDDED_SCHEDULER=false on the WEB service specifically, so it
stops running these jobs itself — otherwise both processes run every
scheduled job on every cycle, double-billing paid APIs (Google Places/
Vision) and double-writing data (duplicate PlaceSignal rows, etc).

Run via:
    python -m app.scheduler_worker
"""
from __future__ import annotations

import logging
import signal
import time
from types import FrameType
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

from app.config.settings import settings
from app.scheduler import SCHEDULER_JOB_IDS, create_scheduler

# Same as app/main.py: this process runs the identical scheduled jobs (see
# that module's own Sentry block for the full reasoning), including
# _job_moderation_queue_health_check's logger.error calls — without this,
# once the scheduler moves here those errors would never reach Sentry at
# all, since main.py's Sentry init only runs in the web process. No
# FastApiIntegration/StarletteIntegration here — there's no ASGI app in
# this process — but sentry_sdk's default integrations (left enabled)
# already include LoggingIntegration, which is what actually captures
# logger.error as events.
if settings.sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=0.1,
        send_default_pii=False,
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("lavish.scheduler_worker")

_shutdown_requested = False


def configured_job_allowlist(raw: str) -> set[str]:
    return {item.strip() for item in raw.split(",") if item.strip()}


def create_worker_scheduler() -> BackgroundScheduler | None:
    """Return the guarded standalone scheduler, or None while disabled.

    Enabling the process without naming jobs is an error rather than an
    implicit "run everything" fallback. A typo is also fatal so operators do
    not mistake an inert worker for a successful partial rollout.
    """
    if not settings.scheduler_worker_enabled:
        return None

    allowlist = configured_job_allowlist(settings.scheduler_job_allowlist)
    if not allowlist:
        raise RuntimeError(
            "scheduler job allowlist is empty while SCHEDULER_WORKER_ENABLED=true"
        )

    unknown = sorted(allowlist - set(SCHEDULER_JOB_IDS))
    if unknown:
        raise RuntimeError(f"Unknown scheduler job IDs: {', '.join(unknown)}")

    return create_scheduler(job_allowlist=allowlist)


def _handle_shutdown_signal(signum: int, frame: Optional[FrameType]) -> None:
    global _shutdown_requested
    logger.info("scheduler_worker_shutdown_signal signum=%s", signum)
    _shutdown_requested = True


def run_scheduler_worker() -> None:
    global _shutdown_requested
    _shutdown_requested = False

    # SIGTERM is what Railway sends on deploy/restart — without handling it,
    # the process dies immediately and scheduler.shutdown(wait=True) never
    # gets a chance to let an in-flight job finish cleanly.
    signal.signal(signal.SIGTERM, _handle_shutdown_signal)
    signal.signal(signal.SIGINT, _handle_shutdown_signal)

    # A signal delivered in the window right after registering the handlers
    # above but before scheduler.start() below would otherwise still run
    # start() unconditionally, then immediately fall into
    # scheduler.shutdown(wait=True) on a scheduler whose background threads
    # may not have finished initializing yet. Bail out before starting at
    # all if that already happened.
    if _shutdown_requested:
        logger.info("scheduler_worker_shutdown_before_start")
        return

    scheduler = create_worker_scheduler()

    if scheduler is None:
        logger.warning("scheduler_worker_disabled no_jobs_will_run")
        while not _shutdown_requested:
            time.sleep(1)
        logger.info("scheduler_worker_stopped")
        return

    if _shutdown_requested:
        logger.info("scheduler_worker_shutdown_before_start")
        return

    scheduler.start()
    logger.info("scheduler_worker_started jobs=%s", len(scheduler.get_jobs()))

    try:
        while not _shutdown_requested:
            time.sleep(1)
    finally:
        scheduler.shutdown(wait=True)
        logger.info("scheduler_worker_stopped")


if __name__ == "__main__":
    run_scheduler_worker()
