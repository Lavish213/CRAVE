from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.services.network.http_fetcher import fetch


logger = logging.getLogger(__name__)

MAX_HTML_SIZE = 5_000_000
MIN_HTML_SIZE = 200


def _validate_response(response: httpx.Response, url: str) -> None:

    if response is None:
        raise RuntimeError(f"http_response_missing url={url}")

    status = response.status_code

    if status >= 400:
        raise RuntimeError(f"http_error url={url} status={status}")

    content_type = response.headers.get("content-type", "").lower()

    if content_type and "html" not in content_type:
        if "json" in content_type:
            raise RuntimeError(f"json_instead_of_html url={url}")
        raise RuntimeError(
            f"non_html_response url={url} content_type={content_type}"
        )


def _read_html(response: httpx.Response, url: str) -> str:

    try:
        html = response.text
    except Exception as exc:
        raise RuntimeError(
            f"html_decode_failed url={url}"
        ) from exc

    if not html:
        raise RuntimeError(f"empty_html url={url}")

    size = len(html)

    if size < MIN_HTML_SIZE:
        raise RuntimeError(
            f"html_too_small url={url} size={size}"
        )

    if size > MAX_HTML_SIZE:
        raise RuntimeError(
            f"html_too_large url={url} size={size}"
        )

    return html


def fetch_html(
    url: str,
    *,
    extra_headers: Optional[dict[str, str]] = None,
) -> str:

    try:

        response = fetch(
            url,
            method="GET",
            headers=extra_headers,
        )

    except Exception as exc:

        logger.debug(
            "menu_html_fetch_failed url=%s error=%s",
            url,
            exc,
        )

        raise

    _validate_response(response, url)

    html = _read_html(response, url)

    logger.debug(
        "menu_html_fetched url=%s size=%s",
        url,
        len(html),
    )

    return html