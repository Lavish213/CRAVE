from __future__ import annotations

import logging
from typing import List, Optional

from app.services.network.http_fetcher import fetch

from app.services.menu.contracts import ExtractedMenuItem
from app.services.menu.extraction.iframe_menu_detector import detect_menu_iframes
from app.services.menu.extraction.provider_detector import detect_provider
from app.services.menu.extraction.html_menu_extractor import extract_menu_from_html

from app.services.menu.providers.toast_extractor import extract_toast_menu
from app.services.menu.providers.clover_extractor import extract_clover_menu
from app.services.menu.providers.chownow_extractor import extract_chownow_menu
from app.services.menu.providers.popmenu_extractor import extract_popmenu_menu


logger = logging.getLogger(__name__)


MAX_IFRAMES = 8
MAX_ITEMS = 1500


_PROVIDER_EXTRACTORS = {
    "toast": extract_toast_menu,
    "clover": extract_clover_menu,
    "chownow": extract_chownow_menu,
    "popmenu": extract_popmenu_menu,
}


# ---------------------------------------------------------
# dedupe
# ---------------------------------------------------------

def _dedupe(items: List[ExtractedMenuItem]) -> List[ExtractedMenuItem]:

    seen = set()
    unique: List[ExtractedMenuItem] = []

    for item in items:

        key = (
            f"{(item.name or '').strip().lower()}|"
            f"{(item.price or '').strip()}|"
            f"{(item.section or '').strip().lower()}"
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(item)

        if len(unique) >= MAX_ITEMS:
            break

    return unique


# ---------------------------------------------------------
# fetch iframe page
# ---------------------------------------------------------

def _fetch_iframe_html(url: str) -> Optional[str]:

    try:

        response = fetch(url)

        if response.status_code != 200:
            return None

        return response.text

    except Exception as exc:

        logger.debug(
            "iframe_fetch_failed url=%s error=%s",
            url,
            exc,
        )

        return None


# ---------------------------------------------------------
# provider extraction
# ---------------------------------------------------------

def _extract_from_provider(
    html: str,
    url: str,
) -> List[ExtractedMenuItem]:

    provider = detect_provider(html, url)

    if not provider:
        return []

    extractor = _PROVIDER_EXTRACTORS.get(provider)

    if not extractor:
        return []

    try:

        items = extractor(html=html, url=url)

        return items

    except Exception as exc:

        logger.debug(
            "iframe_provider_extraction_failed provider=%s error=%s",
            provider,
            exc,
        )

        return []


# ---------------------------------------------------------
# main extractor
# ---------------------------------------------------------

def extract_iframe_menus(
    html: str,
    base_url: Optional[str] = None,
) -> List[ExtractedMenuItem]:

    if not html:
        return []

    iframe_urls = detect_menu_iframes(html, base_url)

    if not iframe_urls:
        return []

    items: List[ExtractedMenuItem] = []

    for iframe_url in iframe_urls[:MAX_IFRAMES]:

        iframe_html = _fetch_iframe_html(iframe_url)

        if not iframe_html:
            continue

        # provider menu first
        provider_items = _extract_from_provider(
            iframe_html,
            iframe_url,
        )

        if provider_items:

            items.extend(provider_items)
            continue

        # fallback html extraction
        try:

            result = extract_menu_from_html(
                iframe_html,
                iframe_url,
            )

            if result and result.items:

                items.extend(result.items)

        except Exception as exc:

            logger.debug(
                "iframe_html_extraction_failed url=%s error=%s",
                iframe_url,
                exc,
            )

    items = _dedupe(items)

    if items:

        logger.info(
            "iframe_menu_extracted items=%s",
            len(items),
        )

    return items