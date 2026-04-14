from __future__ import annotations

import logging
from typing import Optional


logger = logging.getLogger(__name__)


# Known domain/URL patterns → site type
_PROVIDER_PATTERNS = {
    "toasttab.com": "toast",
    "order.toasttab.com": "toast",
    "popmenu.com": "popmenu",
    "ordering.chownow.com": "chownow",
    "clover.com": "clover",
    "squareup.com": "square",
    "olo.com": "olo",
}


def classify_site(url: Optional[str]) -> Optional[str]:
    """
    Classify a restaurant website URL into a known site/provider type.

    Returns a short lowercase string (e.g. "toast", "spa", "static")
    or None if classification is not possible.
    """

    if not url:
        return None

    try:
        url_lower = url.lower()

        for pattern, site_type in _PROVIDER_PATTERNS.items():
            if pattern in url_lower:
                return site_type

        return "http"

    except Exception as exc:
        logger.debug("site_classifier_failed url=%s error=%s", url, exc)
        return None
