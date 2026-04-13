from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from app.services.network.http_fetcher import fetch


logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# Limits
# ---------------------------------------------------------

MAX_ENDPOINT_REPLAYS = 15
MAX_RESPONSE_BYTES = 5_000_000
REQUEST_TIMEOUT = 15


# ---------------------------------------------------------
# Headers
# ---------------------------------------------------------

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
}


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _safe_json(response_text: str) -> Optional[object]:
    if not response_text:
        return None

    try:
        return json.loads(response_text)
    except Exception:
        return None


def _normalize_payload(payload: object) -> Optional[object]:
    if payload is None:
        return None

    if isinstance(payload, dict):
        for key in ("data", "result", "menu", "menus", "payload"):
            if key in payload and isinstance(payload[key], (dict, list)):
                return payload[key]

        return payload

    if isinstance(payload, list):
        return payload

    return None


def _looks_valid_payload(payload: object) -> bool:
    if payload is None:
        return False

    if isinstance(payload, list):
        return len(payload) > 0

    if isinstance(payload, dict):
        return len(payload.keys()) > 0

    return False


def _safe_response_text(response) -> Optional[str]:
    try:
        return response.text
    except Exception:
        try:
            return response.content.decode("utf-8", errors="ignore")
        except Exception:
            return None


def _is_graphql_endpoint(url: str) -> bool:
    return "graphql" in url.lower()


def _origin_from_url(url: str) -> Optional[str]:
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return None
        return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        return None


def _safe_method(value: Any) -> str:
    try:
        method = str(value or "GET").upper().strip()
    except Exception:
        return "GET"

    if method not in {"GET", "POST"}:
        return "GET"

    return method


def _safe_body(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, dict):
        return value
    return None


# ---------------------------------------------------------
# Core Request Logic
# ---------------------------------------------------------

def _request_endpoint(
    url: str,
    method: str = "GET",
    body: Optional[Dict[str, Any]] = None,
    referer: Optional[str] = None,
) -> Optional[object]:
    try:
        method = _safe_method(method)
        request_body = _safe_body(body)
        request_referer = referer or _origin_from_url(url)

        # ---------------------------------------------------------
        # Attempt request
        # ---------------------------------------------------------

        if method == "POST":
            response = fetch(
                url,
                method="POST",
                mode="api",
                json=request_body or {},
                headers=DEFAULT_HEADERS,
                timeout=REQUEST_TIMEOUT,
                referer=request_referer,
            )
        else:
            response = fetch(
                url,
                method="GET",
                mode="api",
                headers=DEFAULT_HEADERS,
                timeout=REQUEST_TIMEOUT,
                referer=request_referer,
            )

        if response.status_code != 200:
            return None

        if len(response.content or b"") > MAX_RESPONSE_BYTES:
            logger.debug(
                "js_endpoint_response_too_large url=%s bytes=%s",
                url,
                len(response.content),
            )
            return None

        text = _safe_response_text(response)

        if not text:
            return None

        payload = _safe_json(text)
        payload = _normalize_payload(payload)

        if _looks_valid_payload(payload):
            return payload

        # ---------------------------------------------------------
        # Fallback: GraphQL POST retry
        # ---------------------------------------------------------

        if method == "GET" and _is_graphql_endpoint(url):
            try:
                response = fetch(
                    url,
                    method="POST",
                    mode="graphql",
                    json=request_body or {"query": "{ __typename }"},
                    headers=DEFAULT_HEADERS,
                    timeout=REQUEST_TIMEOUT,
                    referer=request_referer,
                )

                if response.status_code != 200:
                    return None

                if len(response.content or b"") > MAX_RESPONSE_BYTES:
                    logger.debug(
                        "js_graphql_response_too_large url=%s bytes=%s",
                        url,
                        len(response.content),
                    )
                    return None

                text = _safe_response_text(response)
                payload = _safe_json(text)
                payload = _normalize_payload(payload)

                if _looks_valid_payload(payload):
                    return payload

            except Exception as exc:
                logger.debug(
                    "js_graphql_retry_failed url=%s error=%s",
                    url,
                    exc,
                )

        return None

    except Exception as exc:
        logger.debug(
            "js_endpoint_request_failed url=%s error=%s",
            url,
            exc,
        )
        return None


# ---------------------------------------------------------
# Public API
# ---------------------------------------------------------

def replay_js_endpoints(
    ranked_endpoints: List[Dict[str, Any]],
    referer: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Execute ranked JS endpoints and return payloads.

    Input endpoint shape:
        {
            "url": str,
            "method": "GET" | "POST",
            "body": optional dict,
            ...
        }
    """

    results: List[Dict[str, Any]] = []
    seen_keys = set()

    if not ranked_endpoints:
        return results

    for endpoint in ranked_endpoints[:MAX_ENDPOINT_REPLAYS]:
        url = endpoint.get("url")
        method = _safe_method(endpoint.get("method", "GET"))
        body = _safe_body(endpoint.get("body"))

        if not url:
            continue

        dedupe_key = (
            str(url).strip(),
            method,
            json.dumps(body, sort_keys=True, separators=(",", ":")) if body else "",
        )

        if dedupe_key in seen_keys:
            continue

        seen_keys.add(dedupe_key)

        payload = _request_endpoint(
            url=url,
            method=method,
            body=body,
            referer=referer,
        )

        if not payload:
            continue

        results.append(
            {
                "url": url,
                "method": method,
                "payload": payload,
                "status": 200,
            }
        )

        logger.debug("js_endpoint_replay_success url=%s method=%s", url, method)

    logger.info("js_endpoint_replay_complete results=%s", len(results))

    return results