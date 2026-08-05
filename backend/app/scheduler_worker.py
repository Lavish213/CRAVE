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

from app.scheduler import create_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("lavish.scheduler_worker")

_shutdown_requested = False


def _handle_shutdown_signal(signum: int, frame: Optional[FrameType]) -> None:
    global _shutdown_requested
    logger.info("scheduler_worker_shutdown_signal signum=%s", signum)
    _shutdown_requested = True


def run_scheduler_worker() -> None:
    # SIGTERM is what Railway sends on deploy/restart — without handling it,
    # the process dies immediately and scheduler.shutdown(wait=True) never
    # gets a chance to let an in-flight job finish cleanly.
    signal.signal(signal.SIGTERM, _handle_shutdown_signal)
    signal.signal(signal.SIGINT, _handle_shutdown_signal)

    scheduler = create_scheduler()
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
