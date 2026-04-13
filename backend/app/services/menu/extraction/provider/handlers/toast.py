from __future__ import annotations

import logging
import re
from typing import List, Optional, Any

from app.services.menu.contracts import ExtractedMenuItem
from app.services.network.http_fetcher import fetch
from app.services.menu.extraction.js.js_menu_payload_adapter import convert_payload_to_menu_items
from app.services.menu.extraction.js.js_hydration_detector import detect_hydration_state


logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# STRICT SLUG EXTRACTION
# ---------------------------------------------------------

def _extract_slug(url: str) -> Optional[str]:
    try:
        parts = url.rstrip("/").split("/")

        # expected: /local/<slug>
        if "local" in parts:
            return parts[-1]

        return None

    except Exception:
        return None


# ---------------------------------------------------------
# HARD FAIL LOGGER
# ---------------------------------------------------------

def _fail(reason: str, url: Optional[str]):
    logger.warning("toast_fail reason=%s url=%s", reason, url)
    return []


# ---------------------------------------------------------
# HYDRATION FALLBACK PARSER (extra safety)
# ---------------------------------------------------------

def _extract_embedded_json(html: str) -> List[Any]:
    payloads: List[Any] = []

    try:
        # crude but effective fallback (window.__APOLLO_STATE__ / etc.)
        matches = re.findall(r"window\.__.*?=\s*({.*?});", html, re.DOTALL)

        for m in matches:
            payloads.append(m)

    except Exception:
        pass

    return payloads


# ---------------------------------------------------------
# HANDLER (FINAL)
# ---------------------------------------------------------

def handle_toast(
    html: str,
    url: Optional[str],
) -> List[ExtractedMenuItem]:

    if not url:
        return _fail("no_url", url)

    slug = _extract_slug(url)

    if not slug:
        return _fail("bad_slug", url)

    # 🔥 REAL ENTRY POINT (NOT FAKE API)
    page_url = f"https://order.toasttab.com/online/{slug}"

    try:
        response = fetch(
            page_url,
            method="GET",
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "text/html",
                "Referer": "https://www.toasttab.com/",
            },
        )

        if response.status_code != 200:
            return _fail(f"bad_status_{response.status_code}", url)

        html = response.text

        if not html:
            return _fail("empty_html", url)

        # ---------------------------------------------------------
        # 1. PRIMARY: hydration detector
        # ---------------------------------------------------------

        try:
            hydration = detect_hydration_state(html)

            if isinstance(hydration, dict):
                raw = hydration.get("raw")

                if raw:
                    items = convert_payload_to_menu_items(raw)

                    if items:
                        logger.info("toast_success_hydration url=%s items=%s", url, len(items))
                        return items[:1500]

        except Exception as exc:
            logger.debug("toast_hydration_failed error=%s", exc)

        # ---------------------------------------------------------
        # 2. SECONDARY: embedded JSON scan
        # ---------------------------------------------------------

        payloads = _extract_embedded_json(html)

        for payload in payloads:
            try:
                items = convert_payload_to_menu_items(payload)

                if items:
                    logger.info("toast_success_embedded url=%s items=%s", url, len(items))
                    return items[:1500]

            except Exception:
                continue

        return _fail("no_items_found", url)

    except Exception as exc:
        return _fail(f"exception_{type(exc).__name__}", url)