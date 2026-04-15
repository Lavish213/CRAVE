from __future__ import annotations

import logging
from typing import List, Optional

from app.services.menu.contracts import ExtractedMenuItem
from app.services.menu.providers.chownow_extractor import extract_chownow_menu


logger = logging.getLogger(__name__)


def handle_chownow(
    html: str,
    url: Optional[str],
) -> Optional[List[ExtractedMenuItem]]:
    """
    ChowNow handler — thin wrapper around the legacy extract_chownow_menu extractor.
    Tries the embedded menu_url API first, then falls back to parsing
    window.__INITIAL_STATE__ / categories JSON from the page HTML.
    """

    try:
        items = extract_chownow_menu(html=html, url=url)

        if not items:
            logger.debug("chownow_handler_no_items url=%s", url)
            return None

        logger.info("chownow_handler_success url=%s items=%s", url, len(items))
        return items

    except Exception as exc:
        logger.debug("chownow_handler_failed url=%s error=%s", url, exc)
        return None
