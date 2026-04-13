from __future__ import annotations

import logging
from typing import Dict, List


logger = logging.getLogger(__name__)


class NetworkInterceptor:
    """
    Captures API and GraphQL requests during page rendering.

    Used for React / SPA restaurant websites where
    menu data loads through network calls instead of HTML.
    """

    def __init__(self) -> None:
        self.api_calls: List[Dict] = []
        self.graphql_calls: List[Dict] = []

    # -----------------------------------------------------
    # Record HTTP requests
    # -----------------------------------------------------

    def record_request(
        self,
        url: str,
        method: str,
        response_json: Dict | None,
    ) -> None:

        try:

            entry = {
                "url": url,
                "method": method,
                "response": response_json,
            }

            if "graphql" in url.lower():

                self.graphql_calls.append(entry)

            else:

                self.api_calls.append(entry)

        except Exception as exc:

            logger.debug(
                "network_interceptor_failed url=%s error=%s",
                url,
                exc,
            )

    # -----------------------------------------------------
    # Export captured data
    # -----------------------------------------------------

    def export(self) -> Dict:

        return {
            "api_calls": self.api_calls,
            "graphql_calls": self.graphql_calls,
        }