from __future__ import annotations

import logging
from typing import Optional

from app.services.network.http_fetcher import fetch


logger = logging.getLogger(__name__)


SEARCH_ENDPOINT = "https://duckduckgo.com/html"


def discover_websites(
    *,
    name: Optional[str],
    address: Optional[str],
    lat: Optional[float] = None,
    lon: Optional[float] = None,
) -> Optional[str]:
    """
    Attempts to discover the official website of a restaurant
    using simple search queries.
    """

    if not name:
        return None

    query = name

    if address:
        query = f"{name} {address}"

    try:

        response = fetch(
            SEARCH_ENDPOINT,
            method="GET",
            params={"q": query},
        )

        if response.status_code != 200:
            return None

        html = response.text.lower()

        # very simple heuristic
        for line in html.splitlines():

            if "http" in line and "result__a" in line:

                start = line.find("http")

                end = line.find('"', start)

                if start != -1 and end != -1:

                    url = line[start:end]

                    if "duckduckgo" not in url:
                        return url

    except Exception as exc:

        logger.debug(
            "website_discovery_failed name=%s error=%s",
            name,
            exc,
        )

    return None