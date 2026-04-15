from __future__ import annotations

import logging
from typing import List, Optional

from app.services.menu.contracts import ExtractedMenuItem
from app.services.menu.providers.clover_extractor import extract_clover_menu


logger = logging.getLogger(__name__)


def handle_clover(
    html: str,
    url: Optional[str],
) -> Optional[List[ExtractedMenuItem]]:
    """
    Clover handler — thin wrapper around the legacy extract_clover_menu extractor.
    Parses embedded JSON hydration blobs (window.__PRELOADED_STATE__, etc.) from
    the Clover online-ordering page HTML.
    """

    try:
        items = extract_clover_menu(html=html, url=url)

        if not items:
            logger.debug("clover_handler_no_items url=%s", url)
            return None

        logger.info("clover_handler_success url=%s items=%s", url, len(items))
        return items

    except Exception as exc:
        logger.debug("clover_handler_failed url=%s error=%s", url, exc)
        return None
