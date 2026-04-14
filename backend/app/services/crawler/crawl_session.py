from __future__ import annotations

import logging
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


class CrawlSession:
    """
    Executes a crawl of a single URL using the given strategy.

    Minimal stub — extend with real browser/HTTP logic as needed.
    """

    def __init__(
        self,
        *,
        url: str,
        strategy: Optional[str] = None,
    ) -> None:
        self.url = url
        self.strategy = strategy or "http"

    def run(self) -> Dict[str, Any]:
        """
        Execute the crawl and return a result dict.
        Returns an empty result if the crawl is not implemented for this strategy.
        """
        logger.debug(
            "crawl_session_run url=%s strategy=%s",
            self.url,
            self.strategy,
        )

        return {
            "url": self.url,
            "strategy": self.strategy,
            "html": None,
            "items": [],
            "success": False,
        }
