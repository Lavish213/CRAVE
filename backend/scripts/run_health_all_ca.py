from __future__ import annotations

import logging
import time

from config.city_loader import load_region_map
from scripts.run_health_region import run_region


logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


# ---------------------------------------------------------
# State Runner
# ---------------------------------------------------------

def run_all_california() -> None:

    region_map = load_region_map()

    regions = sorted(region_map.keys())

    logger.info(
        "health_state_start regions=%s",
        len(regions),
    )

    start = time.time()

    success = 0
    failed = 0

    for region in regions:

        try:

            logger.info(
                "health_state_region_start region=%s",
                region,
            )

            run_region(region)

            success += 1

        except Exception as exc:

            failed += 1

            logger.exception(
                "health_state_region_failed region=%s error=%s",
                region,
                exc,
            )

    elapsed = round(time.time() - start, 2)

    logger.info(
        "health_state_complete success=%s failed=%s seconds=%s",
        success,
        failed,
        elapsed,
    )


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------

def main() -> None:

    run_all_california()


if __name__ == "__main__":
    main()