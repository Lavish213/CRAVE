from __future__ import annotations

import logging
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


# Known crawl strategies
STRATEGY_HTTP = "http"
STRATEGY_BROWSER = "browser"
STRATEGY_API = "api"


class StrategyEngine:
    """
    Chooses the best crawl strategy for a given site type.

    Minimal stub — extend with heuristics as needed.
    """

    def choose_strategy(
        self,
        *,
        site_type: Optional[str] = None,
        entity: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Return a strategy name for the given site type.
        """

        if not site_type:
            return STRATEGY_HTTP

        site_type = site_type.lower()

        if site_type in {"spa", "react", "next", "angular", "vue"}:
            return STRATEGY_BROWSER

        if site_type in {"api", "toast", "square", "olo", "popmenu"}:
            return STRATEGY_API

        return STRATEGY_HTTP
