from __future__ import annotations

import logging
from typing import Dict, List, Optional
from urllib.parse import urlparse

from app.services.network.http_fetcher import fetch


logger = logging.getLogger(__name__)


MAX_FETCHED_BUNDLES = 12
MAX_BUNDLE_SIZE_BYTES = 3 * 1024 * 1024

ALLOWED_CONTENT_TYPE_TOKENS = (
    "javascript",
    "ecmascript",
    "text/plain",
    "application/octet-stream",
)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _content_type_allows_bundle(content_type: str) -> bool:
    lowered = (content_type or "").lower()
    if not lowered:
        return True
    return any(token in lowered for token in ALLOWED_CONTENT_TYPE_TOKENS)


def _body_size_allows_bundle(content: bytes) -> bool:
    return bool(content) and len(content) <= MAX_BUNDLE_SIZE_BYTES


def _looks_like_js(text: str) -> bool:
    if not text:
        return False

    sample = text[:500].lower()

    if "<html" in sample or "<!doctype" in sample:
        return False

    if "function" in sample or "const " in sample or "var " in sample:
        return True

    if "webpack" in sample or "__next" in sample:
        return True

    return True


def _safe_get_text(response) -> Optional[str]:
    try:
        text = response.text
    except Exception:
        try:
            text = response.content.decode("utf-8", errors="ignore")
        except Exception:
            return None

    if not text or not text.strip():
        return None

    return text


def _same_domain_priority(url: str, first_domain: Optional[str]) -> int:
    try:
        domain = urlparse(url).netloc.lower()
        if first_domain and domain == first_domain:
            return 1
    except Exception:
        pass
    return 0


# ---------------------------------------------------------
# 🔥 CORE FETCH (PROD SAFE)
# ---------------------------------------------------------

def _fetch_single_bundle(
    url: str,
    referer: Optional[str],
) -> Optional[str]:

    if not url:
        return None

    try:
        safe_referer = referer or url

        # ---------------------------------------------------------
        # PRIMARY: browser-like script request
        # ---------------------------------------------------------

        response = fetch(
            url,
            method="GET",
            mode="script",
            referer=safe_referer,
        )

        # ---------------------------------------------------------
        # RETRY: anti-bot fallback
        # ---------------------------------------------------------

        if response.status_code in (403, 429):
            logger.debug("js_bundle_retry url=%s", url)

            response = fetch(
                url,
                method="GET",
                mode="document",
                referer=safe_referer,
            )

        if response.status_code != 200:
            logger.debug(
                "js_bundle_bad_status url=%s status=%s",
                url,
                response.status_code,
            )
            return None

        content_type = response.headers.get("content-type", "")

        if not _content_type_allows_bundle(content_type):
            logger.debug(
                "js_bundle_bad_type url=%s type=%s",
                url,
                content_type,
            )
            return None

        content = response.content or b""

        if not _body_size_allows_bundle(content):
            logger.debug(
                "js_bundle_too_large url=%s size=%s",
                url,
                len(content),
            )
            return None

        text = _safe_get_text(response)

        if not text:
            logger.debug("js_bundle_empty url=%s", url)
            return None

        if not _looks_like_js(text):
            logger.debug("js_bundle_not_js url=%s", url)
            return None

        return text

    except Exception as exc:
        logger.debug("js_bundle_fetch_failed url=%s error=%s", url, exc)
        return None


# ---------------------------------------------------------
# Public API
# ---------------------------------------------------------

def fetch_js_bundles(
    bundle_urls: List[str],
    referer: Optional[str] = None,
) -> Dict[str, str]:
    """
    🔥 PRODUCTION JS BUNDLE FETCHER

    Fixes:
    - referer support (CRITICAL for anti-bot)
    - browser-like fetch mode
    - retry on 403/429
    - strict validation
    """

    fetched: Dict[str, str] = {}

    if not bundle_urls:
        return fetched

    # ---------------------------------------------------------
    # Deduplicate
    # ---------------------------------------------------------

    unique_urls = list(dict.fromkeys(bundle_urls))

    # ---------------------------------------------------------
    # Domain priority
    # ---------------------------------------------------------

    first_domain = None

    try:
        if unique_urls:
            first_domain = urlparse(unique_urls[0]).netloc.lower()
    except Exception:
        pass

    unique_urls.sort(
        key=lambda u: _same_domain_priority(u, first_domain),
        reverse=True,
    )

    # ---------------------------------------------------------
    # Fetch loop
    # ---------------------------------------------------------

    for url in unique_urls[:MAX_FETCHED_BUNDLES]:

        if not url or url in fetched:
            continue

        text = _fetch_single_bundle(url, referer)

        if not text:
            continue

        fetched[url] = text

    logger.debug(
        "js_bundle_fetch_complete requested=%s fetched=%s",
        min(len(unique_urls), MAX_FETCHED_BUNDLES),
        len(fetched),
    )

    return fetched