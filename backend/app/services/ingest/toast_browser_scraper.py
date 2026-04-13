from __future__ import annotations

import json
import logging
from typing import List, Dict, Any, Set, Optional

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

_TOAST_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"
_JSON_CT_MARKERS = ("application/json", "application/graphql-response+json")
_TOAST_HOST_MARKERS = ("toasttab.com", "ws-api.toasttab.com", "cdn.toasttab.com")
_APOLLO_STATE_KEYS = (
    "__APOLLO_STATE__",
    "__NEXT_DATA__",
    "__NUXT__",
    "__INITIAL_STATE__",
)
_MAX_DEBUG_PRINT = 5


def _is_toast_url(url: str) -> bool:
    lower = url.lower()
    return any(marker in lower for marker in _TOAST_HOST_MARKERS)


def _json_like_content_type(content_type: str) -> bool:
    lower = content_type.lower()
    return any(marker in lower for marker in _JSON_CT_MARKERS)


def _safe_json_loads(value: str) -> Optional[Any]:
    try:
        return json.loads(value)
    except Exception:
        return None


def _stable_key(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    except Exception:
        return str(value)


def _append_unique_dict_payload(
    out: List[Dict[str, Any]],
    seen: Set[str],
    payload: Any,
) -> None:
    if not isinstance(payload, dict):
        return

    key = _stable_key(payload)
    if key in seen:
        return

    seen.add(key)
    out.append(payload)


def _extract_json_objects_from_text(text: str) -> List[Dict[str, Any]]:
    decoder = json.JSONDecoder()
    results: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    idx = 0
    length = len(text)

    while idx < length:
        char = text[idx]

        if char not in "{[":
            idx += 1
            continue

        try:
            obj, end = decoder.raw_decode(text[idx:])
        except Exception:
            idx += 1
            continue

        if isinstance(obj, dict):
            _append_unique_dict_payload(results, seen, obj)
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict):
                    _append_unique_dict_payload(results, seen, item)

        idx += max(end, 1)

    return results


def _normalize_payload_candidates(payload: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    if isinstance(payload, dict):
        _append_unique_dict_payload(out, seen, payload)
        return out

    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                _append_unique_dict_payload(out, seen, item)

    return out


def _extract_window_state_payloads(page) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    for key in _APOLLO_STATE_KEYS:
        try:
            value = page.evaluate(f"typeof window !== 'undefined' ? (window.{key} ?? null) : null")
        except Exception:
            value = None

        for payload in _normalize_payload_candidates(value):
            _append_unique_dict_payload(out, seen, payload)

    try:
        html = page.content()
    except Exception:
        html = ""

    if html:
        for payload in _extract_json_objects_from_text(html):
            _append_unique_dict_payload(out, seen, payload)

    return out


def _collect_network_payloads(page, url: str) -> List[Dict[str, Any]]:
    responses: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    def handle_response(response) -> None:
        try:
            response_url = response.url or ""
            if not _is_toast_url(response_url):
                return

            request = response.request
            resource_type = request.resource_type or ""
            if resource_type not in ("xhr", "fetch", "document", "script"):
                return

            content_type = response.headers.get("content-type", "")
            body_text: Optional[str] = None

            if _json_like_content_type(content_type):
                try:
                    payload = response.json()
                except Exception:
                    body_text = response.text()
                    payload = _safe_json_loads(body_text or "")
            else:
                body_text = response.text()
                payload = _safe_json_loads(body_text or "")

            for candidate in _normalize_payload_candidates(payload):
                _append_unique_dict_payload(responses, seen, candidate)

        except Exception:
            pass

    page.on("response", handle_response)

    logger.info("toast_browser_fetch_start url=%s", url)

    page.goto(url, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)

    try:
        page.mouse.move(200, 200)
    except Exception:
        pass

    for _ in range(3):
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        except Exception:
            pass
        page.wait_for_timeout(1500)

    try:
        page.evaluate("window.scrollTo(0, 0)")
    except Exception:
        pass

    page.wait_for_timeout(3500)

    return responses


# -----------------------------------------------------
# HTML FETCH (fallback / debug)
# -----------------------------------------------------

def fetch_toast_page(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            user_agent=_TOAST_UA,
            viewport={"width": 1280, "height": 900},
        )

        page = context.new_page()

        logger.info("toast_html_fetch_start url=%s", url)

        page.goto(url, timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)

        html = page.content()

        browser.close()

        logger.info("toast_html_fetch_complete url=%s length=%s", url, len(html))

        return html


# -----------------------------------------------------
# GRAPHQL / JSON CAPTURE (MAIN ENGINE)
# -----------------------------------------------------

def fetch_toast_data(url: str) -> List[Dict[str, Any]]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            user_agent=_TOAST_UA,
            viewport={"width": 1280, "height": 900},
        )

        page = context.new_page()

        network_payloads = _collect_network_payloads(page, url)
        state_payloads = _extract_window_state_payloads(page)

        browser.close()

    merged: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    for payload in network_payloads:
        _append_unique_dict_payload(merged, seen, payload)

    for payload in state_payloads:
        _append_unique_dict_payload(merged, seen, payload)

    logger.info(
        "toast_browser_fetch_complete url=%s network_payloads=%s state_payloads=%s merged=%s",
        url,
        len(network_payloads),
        len(state_payloads),
        len(merged),
    )

    return merged


# -----------------------------------------------------
# DEBUG TOOL
# -----------------------------------------------------

def debug_toast_data(url: str) -> None:
    data = fetch_toast_data(url)

    print(f"\nTOTAL RESPONSES: {len(data)}\n")

    if not data:
        print("⚠️ NO DATA CAPTURED")
        print("Checked: network responses + embedded window/app state + HTML JSON blobs")
        return

    for i, d in enumerate(data[:_MAX_DEBUG_PRINT]):
        print(f"--- RESPONSE {i + 1} ---")
        print(d)
        print()