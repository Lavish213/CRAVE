from __future__ import annotations

import logging
from typing import List, Optional

from app.services.menu.contracts import ExtractedMenuItem
from app.services.menu.providers.square_extractor import extract_square_menu


logger = logging.getLogger(__name__)


def handle_square(
    html: str,
    url: Optional[str],
) -> Optional[List[ExtractedMenuItem]]:
    """
    Square handler — thin wrapper around the legacy extract_square_menu extractor.
    Parses window.__PRELOADED_STATE__ / window.Square hydration blobs from
    Square online-ordering page HTML.
    """

    try:
        items = extract_square_menu(html=html, url=url)

        if not items:
            logger.debug("square_handler_no_items url=%s", url)
            return None

        logger.info("square_handler_success url=%s items=%s", url, len(items))
        return items

    except Exception as exc:
        logger.debug("square_handler_failed url=%s error=%s", url, exc)
        return None
