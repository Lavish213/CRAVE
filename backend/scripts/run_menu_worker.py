from __future__ import annotations

import logging
import sys
import time
from pathlib import Path


# =========================================================
# PATH SETUP (SAFE)
# =========================================================

ROOT_DIR = Path(__file__).resolve().parents[2]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("menu_worker_runner")


# =========================================================
# CONFIG
# =========================================================

RESTART_DELAY_SECONDS = 5
HEARTBEAT_INTERVAL = 60


# =========================================================
# RUN LOOP
# =========================================================

def run_loop():

    last_heartbeat = 0

    while True:

        try:
            logger.info("menu_worker_run_start")

            from app.services.workers.menu_worker import run_menu_worker

            run_menu_worker()

            logger.info("menu_worker_run_complete")

        except Exception as exc:

            logger.exception(
                "menu_worker_crashed error=%s",
                exc,
            )

            logger.info(
                "menu_worker_restart_sleep seconds=%s",
                RESTART_DELAY_SECONDS,
            )

            time.sleep(RESTART_DELAY_SECONDS)

        # -------------------------------------------------
        # HEARTBEAT (proves system alive)
        # -------------------------------------------------

        now = time.time()

        if now - last_heartbeat >= HEARTBEAT_INTERVAL:
            logger.info("menu_worker_heartbeat_alive")
            last_heartbeat = now


# =========================================================
# ENTRYPOINT
# =========================================================

def main():

    logger.info("menu_worker_runner_boot")

    run_loop()


if __name__ == "__main__":
    main()