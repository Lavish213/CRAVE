from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("master_worker_runner")


def main():

    logger.info("master_worker_boot")

    from app.workers.master_worker import run_master_worker

    run_master_worker()


if __name__ == "__main__":
    main()