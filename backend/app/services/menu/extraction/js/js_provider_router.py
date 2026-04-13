from __future__ import annotations

import logging
from typing import List, Optional

from app.services.menu.contracts import ExtractedMenuItem
from app.services.menu.extraction.provider.provider_detector import detect_provider

# 🔥 provider handlers
from app.services.menu.extraction.provider.handlers.toast import handle_toast
from app.services.menu.extraction.provider.handlers.popmenu import handle_popmenu


logger = logging.getLogger(__name__)


def route_provider(
    html: str,
    url: Optional[str],
) -> Optional[List[ExtractedMenuItem]]:
    """
    Central routing layer for known providers.

    Rules:
    - MUST work without HTML
    - MUST short-circuit pipeline
    - MUST never throw
    """

    if not url:
        return None

    try:
        provider = detect_provider(html or "", url)
    except Exception as exc:
        logger.debug("provider_detect_failed url=%s error=%s", url, exc)
        return None

    if not provider:
        logger.debug("provider_not_detected url=%s", url)
        return None

    logger.debug("provider_detected url=%s provider=%s", url, provider)

    try:
        # ---------------------------------------------------------
        # TOAST
        # ---------------------------------------------------------
        if provider == "toast":
            items = handle_toast(html or "", url)

            if items:
                logger.info("provider_toast_success url=%s items=%s", url, len(items))
                return items

        # ---------------------------------------------------------
        # POPMENU
        # ---------------------------------------------------------
        if provider == "popmenu":
            items = handle_popmenu(html or "", url)

            if items:
                logger.info("provider_popmenu_success url=%s items=%s", url, len(items))
                return items

        # ---------------------------------------------------------
        # FUTURE PROVIDERS
        # ---------------------------------------------------------
        # if provider == "square":
        #     ...
        # if provider == "olo":
        #     ...

    except Exception as exc:
        logger.debug(
            "provider_handler_failed url=%s provider=%s error=%s",
            url,
            provider,
            exc,
        )

    return None