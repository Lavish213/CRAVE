from __future__ import annotations

import logging
import re
from typing import List, Optional

from app.services.menu.contracts import ExtractedMenuItem
from app.services.network.http_fetcher import fetch
from app.services.menu.extraction.js.js_menu_payload_adapter import convert_payload_to_menu_items


logger = logging.getLogger(__name__)


def _extract_restaurant_id(html: str) -> Optional[str]:
    if not html:
        return None

    try:
        match = re.search(r'"restaurantId"\s*:\s*"([^"]+)"', html)
        if match:
            return match.group(1)
    except Exception:
        return None

    return None


def handle_popmenu(
    html: str,
    url: Optional[str],
) -> Optional[List[ExtractedMenuItem]]:
    """
    Popmenu handler:
    - Uses HTML to extract restaurantId
    - Then calls API directly
    """

    if not url:
        return None

    rest_id = _extract_restaurant_id(html)

    if not rest_id:
        logger.debug("popmenu_no_restaurant_id url=%s", url)
        return None

    api_url = f"https://api.popmenu.com/v1/restaurants/{rest_id}/menu"

    try:
        response = fetch(
            api_url,
            mode="api",
            referer=url,
            headers={
                "Origin": "https://www.popmenu.com",
            },
        )

        if response.status_code != 200:
            logger.debug(
                "popmenu_api_bad_status url=%s status=%s",
                api_url,
                response.status_code,
            )
            return None

        try:
            data = response.json()
        except Exception:
            logger.debug("popmenu_json_parse_failed url=%s", api_url)
            return None

        items = convert_payload_to_menu_items(data)

        if not items:
            logger.debug("popmenu_no_items url=%s", api_url)
            return None

        logger.info("popmenu_success url=%s items=%s", url, len(items))
        return items

    except Exception as exc:
        logger.debug("popmenu_handler_failed url=%s error=%s", url, exc)
        return None