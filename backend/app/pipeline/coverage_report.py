from __future__ import annotations

import logging
from typing import Dict, Iterable


logger = logging.getLogger(__name__)


class CoverageReport:
    """
    Generates pipeline coverage metrics.

    Used for:
    - system health monitoring
    - discovery coverage tracking
    - crawl success analysis
    """

    def generate(
        self,
        entities: Iterable[Dict],
    ) -> Dict:

        total = 0
        with_website = 0
        crawled = 0
        with_snapshots = 0
        with_schema = 0

        for entity in entities:

            total += 1

            if entity.get("website"):
                with_website += 1

            if entity.get("crawl"):
                crawled += 1

            if entity.get("snapshots"):
                with_snapshots += 1

            if entity.get("schema"):
                with_schema += 1

        report = {
            "total_entities": total,
            "with_website": with_website,
            "crawled": crawled,
            "with_snapshots": with_snapshots,
            "with_schema": with_schema,
        }

        logger.info(
            "coverage_report_generated total=%s websites=%s crawled=%s",
            total,
            with_website,
            crawled,
        )

        return report