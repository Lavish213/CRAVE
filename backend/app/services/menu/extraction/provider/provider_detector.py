from __future__ import annotations

import logging
import re
from typing import Optional


logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# URL-based provider patterns (fast path)
# ---------------------------------------------------------

_URL_PATTERNS = [
    ("toast", re.compile(r"toasttab\.com", re.I)),
    ("toast", re.compile(r"order\.toasttab\.com", re.I)),
    ("popmenu", re.compile(r"popmenu\.com", re.I)),
    ("chownow", re.compile(r"ordering\.chownow\.com", re.I)),
    ("clover", re.compile(r"clover\.com/online-ordering", re.I)),
    ("square", re.compile(r"squareup\.com", re.I)),
    ("olo", re.compile(r"olo\.com", re.I)),
    ("grubhub", re.compile(r"grubhub\.com", re.I)),
    ("doordash", re.compile(r"doordash\.com", re.I)),
    ("ubereats", re.compile(r"ubereats\.com", re.I)),
]


# ---------------------------------------------------------
# HTML-based provider signals (slower fallback)
# ---------------------------------------------------------

_HTML_SIGNALS = [
    ("toast", re.compile(r"toasttab|toast-tab|__TOAST__", re.I)),
    ("popmenu", re.compile(r"popmenu|pop-menu", re.I)),
    ("chownow", re.compile(r"chownow", re.I)),
    ("clover", re.compile(r"clover\.com", re.I)),
    ("square", re.compile(r"squareup|square-menu", re.I)),
]


# ---------------------------------------------------------
# Public API
# ---------------------------------------------------------

def detect_provider(html: str, url: Optional[str]) -> Optional[str]:
    """
    Detect which third-party ordering/menu provider powers a page.

    Returns a short provider slug (e.g. "toast", "popmenu") or None.
    """

    # 1. Fast URL match
    if url:
        for provider, pattern in _URL_PATTERNS:
            if pattern.search(url):
                logger.debug("provider_detected_by_url provider=%s url=%s", provider, url)
                return provider

    # 2. HTML signal scan (only if html is non-trivial)
    if html and len(html) > 100:
        for provider, pattern in _HTML_SIGNALS:
            if pattern.search(html[:50_000]):
                logger.debug("provider_detected_by_html provider=%s url=%s", provider, url)
                return provider

    return None
