from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin

from app.services.menu.contracts import ExtractedMenuItem
from app.services.menu.extraction.js.js_bundle_cache import get_bundle, store_bundle
from app.services.menu.extraction.js.js_bundle_discovery import discover_js_bundles
from app.services.menu.extraction.js.js_bundle_fetcher import fetch_js_bundles
from app.services.menu.extraction.js.js_bundle_parser import parse_multiple_bundles
from app.services.menu.extraction.js.js_endpoint_memory import (
    get_remembered_endpoints,
    remember_endpoints,
)
from app.services.menu.extraction.js.js_endpoint_ranker import rank_js_endpoints
from app.services.menu.extraction.js.js_endpoint_replay import replay_js_endpoints
from app.services.menu.extraction.js.js_endpoint_scanner import scan_parsed_bundle_metadata
from app.services.menu.extraction.js.js_hydration_detector import detect_hydration_state
from app.services.menu.extraction.js.js_menu_payload_adapter import convert_payload_to_menu_items


logger = logging.getLogger(__name__)


MAX_BUNDLES = 20
MAX_MENU_ITEMS = 1500
MAX_ENDPOINTS = 120
MAX_WORKERS = 6
MIN_GOOD_ITEM_COUNT = 5


# ---------------------------------------------------------
# Regex
# ---------------------------------------------------------

RAW_ABSOLUTE_URL_REGEX = re.compile(r"""https?://[^\s"'`<>\\]+""", re.IGNORECASE)

RAW_RELATIVE_ENDPOINT_REGEX = re.compile(
    r"""(?:
        ["'`]
        (
            /
            [^"'`<>\s]*
            (?:
                api|menu|menus|graphql|catalog|products|items|categories|order|orders
            )
            [^"'`<>\s]*
        )
        ["'`]
    )""",
    re.IGNORECASE | re.VERBOSE,
)


# ---------------------------------------------------------
# Bundle discovery
# ---------------------------------------------------------

def _collect_bundles(html: str, url: Optional[str]) -> List[str]:
    try:
        return discover_js_bundles(html, url)[:MAX_BUNDLES]
    except Exception as exc:
        logger.debug("js_bundle_discovery_failed url=%s error=%s", url, exc)
        return []


# ---------------------------------------------------------
# Bundle loading (FIXED REFERER PASS)
# ---------------------------------------------------------

def _load_bundles(bundle_urls: List[str], referer: Optional[str]) -> Dict[str, str]:
    results: Dict[str, str] = {}

    def _load(bundle_url: str) -> tuple[str, Optional[str]]:
        try:
            cached = get_bundle(bundle_url)
            if cached:
                return bundle_url, cached

            fetched = fetch_js_bundles([bundle_url], referer=referer)  # ✅ FIX
            text = fetched.get(bundle_url)

            if text:
                store_bundle(bundle_url, text)

            return bundle_url, text

        except Exception:
            return bundle_url, None

    if not bundle_urls:
        return results

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(_load, url) for url in bundle_urls]

        for future in as_completed(futures):
            bundle_url, text = future.result()
            if text:
                results[bundle_url] = text

    return results


# ---------------------------------------------------------
# Endpoint extraction (RAW fallback)
# ---------------------------------------------------------

def _extract_endpoints_from_raw_js(
    bundle_map: Dict[str, str],
    base_url: Optional[str],
) -> List[Dict[str, Any]]:

    endpoints: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    for text in bundle_map.values():

        matches = RAW_ABSOLUTE_URL_REGEX.findall(text)
        matches += RAW_RELATIVE_ENDPOINT_REGEX.findall(text)

        for candidate in matches:

            endpoint_url = candidate.strip()

            if not endpoint_url:
                continue

            if endpoint_url.startswith("/") and base_url:
                endpoint_url = urljoin(base_url, endpoint_url)

            if endpoint_url in seen:
                continue

            if not any(
                k in endpoint_url.lower()
                for k in ("api", "menu", "graphql", "product", "item")
            ):
                continue

            seen.add(endpoint_url)

            endpoints.append(
                {
                    "url": endpoint_url,
                    "method": "POST" if "graphql" in endpoint_url.lower() else "GET",
                }
            )

            if len(endpoints) >= MAX_ENDPOINTS:
                return endpoints

    return endpoints


# ---------------------------------------------------------
# Endpoint discovery
# ---------------------------------------------------------

def _discover_endpoints(bundle_map: Dict[str, str], base_url: Optional[str]) -> List[Dict]:

    endpoints: List[Dict] = []
    seen: Set[str] = set()

    try:
        parsed = parse_multiple_bundles(bundle_map)
        scanned = scan_parsed_bundle_metadata(parsed, base_url or "")

        for endpoint in scanned.get("endpoints", []):
            url = str(endpoint).strip()

            if not url or url in seen:
                continue

            seen.add(url)

            endpoints.append(
                {
                    "url": url,
                    "method": "POST" if "graphql" in url.lower() else "GET",
                }
            )

    except Exception as exc:
        logger.debug("js_parser_failed url=%s error=%s", base_url, exc)

    # fallback
    for e in _extract_endpoints_from_raw_js(bundle_map, base_url):
        if e["url"] not in seen:
            endpoints.append(e)

    return endpoints[:MAX_ENDPOINTS]


# ---------------------------------------------------------
# Payload conversion
# ---------------------------------------------------------

def _convert_payloads(payloads: List[Any], url: Optional[str]) -> List[ExtractedMenuItem]:

    items: List[ExtractedMenuItem] = []

    for payload in payloads:
        try:
            items.extend(convert_payload_to_menu_items(payload))
        except Exception:
            continue

        if len(items) >= MAX_MENU_ITEMS:
            break

    return items[:MAX_MENU_ITEMS]


def _dedupe(items: List[ExtractedMenuItem]) -> List[ExtractedMenuItem]:

    seen: Set[str] = set()
    unique: List[ExtractedMenuItem] = []

    for i in items:
        key = f"{(i.name or '').lower()}|{i.price}|{(i.section or '').lower()}"

        if not i.name or key in seen:
            continue

        seen.add(key)
        unique.append(i)

    return unique


def _extract_payloads(responses: List[Dict]) -> tuple[List[Any], int]:

    payloads = []
    success = 0

    for r in responses:
        payload = r.get("payload")
        if payload:
            payloads.append(payload)
            success += 1

    return payloads, success


# ---------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------

def extract_menu_from_js(
    html: str,
    url: Optional[str] = None,
) -> List[ExtractedMenuItem]:

    if not html:
        return []

    # ---------------------------------------------------------
    # 1. HYDRATION
    # ---------------------------------------------------------

    try:
        hydration = detect_hydration_state(html)
        if hydration and hydration.get("raw"):
            items = _dedupe(_convert_payloads([hydration["raw"]], url))
            if items:
                return items
    except Exception:
        pass

    # ---------------------------------------------------------
    # 2. MEMORY
    # ---------------------------------------------------------

    remembered = get_remembered_endpoints(url) if url else []

    if remembered:
        ranked = rank_js_endpoints(remembered)
        responses = replay_js_endpoints(ranked)
        payloads, _ = _extract_payloads(responses)

        items = _dedupe(_convert_payloads(payloads, url))

        if len(items) >= MIN_GOOD_ITEM_COUNT:
            return items

    # ---------------------------------------------------------
    # 3. FULL JS PIPELINE
    # ---------------------------------------------------------

    bundles = _collect_bundles(html, url)
    bundle_map = _load_bundles(bundles, referer=url)  # ✅ FIX

    if not bundle_map:
        return []

    endpoints = _discover_endpoints(bundle_map, url)

    if not endpoints:
        return []

    ranked = rank_js_endpoints(endpoints)
    responses = replay_js_endpoints(ranked)

    payloads, success = _extract_payloads(responses)
    items = _dedupe(_convert_payloads(payloads, url))

    # memory store
    if items and url:
        try:
            remember_endpoints(url, ranked)
        except Exception:
            pass

    logger.info(
        "JS items=%s endpoints=%s success=%s",
        len(items),
        len(ranked),
        success,
    )

    return items