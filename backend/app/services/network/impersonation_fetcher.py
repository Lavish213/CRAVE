from __future__ import annotations

import logging
from typing import Optional

from curl_cffi import requests


logger = logging.getLogger(__name__)


DEFAULT_TIMEOUT = 10


def fetch_impersonated(
    url: str,
    *,
    method: str = "GET",
    headers: Optional[dict[str, str]] = None,
    timeout: Optional[int] = None,
) -> Optional[str]:
    if not url:
        return None

    timeout = timeout or DEFAULT_TIMEOUT

    try:
        resp = requests.request(
            method=method,
            url=url,
            headers=headers,
            timeout=timeout,
            impersonate="chrome",
        )

        if resp.status_code != 200:
            logger.warning(
                "impersonation_non_200 url=%s status=%s",
                url,
                resp.status_code,
            )
            return None

        text = resp.text or ""

        if not text.strip():
            logger.warning("impersonation_empty_html url=%s", url)
            return None

        logger.info(
            "impersonation_success url=%s size=%s",
            url,
            len(text),
        )

        return text

    except Exception as exc:
        logger.warning(
            "impersonation_failed url=%s error=%s",
            url,
            exc,
        )
        return None