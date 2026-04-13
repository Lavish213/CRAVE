from __future__ import annotations

import logging
from typing import List

from app.services.menu.contracts import ExtractedMenuItem
from app.services.menu.extraction.js.js_menu_payload_adapter import convert_payload_to_menu_items
from app.services.network.http_fetcher import fetch


logger = logging.getLogger(__name__)


def extract_clover_direct(url: str) -> List[ExtractedMenuItem]:

    items: List[ExtractedMenuItem] = []

    try:
        api_url = f"{url.rstrip('/')}/menu"

        response = fetch(
            api_url,
            mode="api",
            referer=url,
        )

        data = response.json()

        converted = convert_payload_to_menu_items(data)

        if converted:
            items.extend(converted)

    except Exception as exc:
        logger.debug("clover_direct_failed url=%s error=%s", url, exc)

    logger.info("clover_direct_items=%s url=%s", len(items), url)

    return items