from __future__ import annotations

import logging
from typing import Dict, Iterable, List

from app.services.crawler.crawl_session import CrawlSession
from app.services.crawler.strategy_engine import StrategyEngine
from app.services.crawler.site_classifier import classify_site


logger = logging.getLogger(__name__)


class CrawlScheduler:
    """
    Schedules crawling of restaurant websites.

    Determines crawl strategy and launches crawl sessions.
    """

    def __init__(self) -> None:
        self.strategy_engine = StrategyEngine()

    # -----------------------------------------------------
    # Entry
    # -----------------------------------------------------

    def run(
        self,
        entities: Iterable[Dict],
    ) -> List[Dict]:

        results: List[Dict] = []

        for entity in entities:

            website = entity.get("website")

            if not website:
                results.append(entity)
                continue

            try:

                site_type = classify_site(website)

                strategy = self.strategy_engine.choose_strategy(
                    site_type=site_type,
                    entity=entity,
                )

                session = CrawlSession(
                    url=website,
                    strategy=strategy,
                )

                crawl_result = session.run()

                entity["crawl"] = crawl_result

            except Exception as exc:

                logger.debug(
                    "crawl_failed website=%s error=%s",
                    website,
                    exc,
                )

            results.append(entity)

        logger.info(
            "crawl_scheduler_complete entities=%s",
            len(results),
        )

        return results