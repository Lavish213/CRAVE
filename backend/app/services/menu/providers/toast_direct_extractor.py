from __future__ import annotations

import logging
import re
from typing import List, Optional

from app.services.menu.contracts import ExtractedMenuItem
from app.services.menu.extraction.js.js_menu_payload_adapter import convert_payload_to_menu_items
from app.services.network.http_fetcher import fetch


logger = logging.getLogger(__name__)


def _build_toast_api_url(url: str) -> Optional[str]:
    try:
        match = re.search(r"toasttab.com/(.*)", url)
        if not match:
            return None

        slug = match.group(1).strip("/")

        return f"https://toasttab.com/{slug}/v3/menu"

    except Exception:
        return None


def extract_toast_direct(url: str) -> List[ExtractedMenuItem]:

    items: List[ExtractedMenuItem] = []

    api_url = _build_toast_api_url(url)

    if not api_url:
        return items

    try:
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
        logger.debug("toast_direct_failed url=%s error=%s", url, exc)

    logger.info("toast_direct_items=%s url=%s", len(items), url)

    return items