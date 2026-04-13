from __future__ import annotations

import logging
import re
from typing import Dict, List, Set


logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# Limits
# ---------------------------------------------------------

MAX_ENDPOINTS_PER_BUNDLE = 100
MAX_TOTAL_ENDPOINTS = 250
MAX_PROVIDER_SIGNALS_PER_BUNDLE = 20
MAX_IMAGE_URLS_PER_BUNDLE = 100
MAX_STORE_IDS_PER_BUNDLE = 50


# ---------------------------------------------------------
# Core Patterns
# ---------------------------------------------------------

RELATIVE_API_PATTERN = re.compile(
    r"""(?P<quote>["'])(?P<url>/(?:api|graphql|menu|menus|product|products|item|items|catalog|category|categories|food|order|ordering)[^"'\\\s<>{}]*) (?P=quote)""",
    re.VERBOSE | re.IGNORECASE,
)

ABSOLUTE_URL_PATTERN = re.compile(
    r"""(?P<quote>["'])(?P<url>https?://[^"'\\\s<>{}]+)(?P=quote)""",
    re.VERBOSE | re.IGNORECASE,
)

GRAPHQL_PATH_PATTERN = re.compile(
    r"""(?P<quote>["'])(?P<url>[^"'\\\s<>{}]*graphql[^"'\\\s<>{}]*) (?P=quote)""",
    re.VERBOSE | re.IGNORECASE,
)

IMAGE_URL_PATTERN = re.compile(
    r"""(?P<quote>["'])(?P<url>(?:https?://[^"'\\\s<>{}]+|/[^"'\\\s<>{}]+)\.(?:jpg|jpeg|png|webp|gif|avif)(?:\?[^"'\\\s<>{}]*)?)(?P=quote)""",
    re.VERBOSE | re.IGNORECASE,
)


# ---------------------------------------------------------
# Endpoint Filtering
# ---------------------------------------------------------

POSITIVE_ENDPOINT_HINTS = (
    "menu",
    "menus",
    "product",
    "products",
    "item",
    "items",
    "catalog",
    "category",
    "categories",
    "food",
    "order",
    "ordering",
    "graphql",
)

NEGATIVE_ENDPOINT_HINTS = (
    "auth",
    "login",
    "logout",
    "session",
    "token",
    "analytics",
    "tracking",
    "metrics",
    "telemetry",
    "sentry",
    "segment",
    "ads",
    "cookie",
)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _clean_url(url: str) -> str:
    url = url.strip().rstrip(",;)")
    return url.split("?")[0]  # strip params for dedupe


def _looks_relevant_endpoint(url: str) -> bool:
    lowered = url.lower()

    if len(lowered) < 4:
        return False

    if any(token in lowered for token in NEGATIVE_ENDPOINT_HINTS):
        return False

    if not any(token in lowered for token in POSITIVE_ENDPOINT_HINTS):
        return False

    # avoid extremely long garbage strings
    if len(lowered) > 200:
        return False

    return True


def _maybe_add_url(target: Set[str], url: str, limit: int) -> None:
    if len(target) >= limit:
        return

    cleaned = _clean_url(url)

    if not cleaned:
        return

    if not _looks_relevant_endpoint(cleaned):
        return

    target.add(cleaned)


# ---------------------------------------------------------
# Bundle Parsing
# ---------------------------------------------------------

def parse_bundle_for_endpoints(bundle_text: str) -> List[str]:

    discovered: Set[str] = set()

    if not bundle_text:
        return []

    for pattern in (RELATIVE_API_PATTERN, GRAPHQL_PATH_PATTERN, ABSOLUTE_URL_PATTERN):

        for match in pattern.finditer(bundle_text):

            _maybe_add_url(
                discovered,
                match.group("url"),
                MAX_ENDPOINTS_PER_BUNDLE,
            )

            if len(discovered) >= MAX_ENDPOINTS_PER_BUNDLE:
                break

    endpoints = sorted(discovered)

    logger.debug("js_bundle_parser_endpoints_discovered count=%s", len(endpoints))

    return endpoints


# ---------------------------------------------------------
# Provider Detection
# ---------------------------------------------------------

PROVIDER_PATTERNS = {
    "toast": re.compile(r"toast(tab)?|toastcdn|api\.toasttab\.com", re.I),
    "clover": re.compile(r"clover|clovercdn|clover\.com", re.I),
    "chownow": re.compile(r"chownow|api\.chownow\.com", re.I),
    "popmenu": re.compile(r"popmenu|api\.popmenu\.com", re.I),
    "square": re.compile(r"square(up)?|squarecdn|squareup\.com", re.I),
    "olo": re.compile(r"\bolo\b|orders\.olo\.com", re.I),
}


def parse_bundle_for_provider_hints(bundle_text: str) -> List[str]:

    providers = []

    if not bundle_text:
        return providers

    for name, pattern in PROVIDER_PATTERNS.items():

        if pattern.search(bundle_text):
            providers.append(name)

    return providers[:MAX_PROVIDER_SIGNALS_PER_BUNDLE]


# ---------------------------------------------------------
# Images
# ---------------------------------------------------------

def parse_bundle_for_image_urls(bundle_text: str) -> List[str]:

    discovered: Set[str] = set()

    if not bundle_text:
        return []

    for match in IMAGE_URL_PATTERN.finditer(bundle_text):

        if len(discovered) >= MAX_IMAGE_URLS_PER_BUNDLE:
            break

        discovered.add(_clean_url(match.group("url")))

    return sorted(discovered)


# ---------------------------------------------------------
# Store IDs
# ---------------------------------------------------------

STORE_ID_PATTERN = re.compile(
    r"""(restaurantId|locationId|storeId|venueId|menuId)["']?\s*[:=]\s*["']?([^"',\s]{1,80})""",
    re.IGNORECASE,
)


def parse_bundle_for_store_ids(bundle_text: str) -> Dict[str, List[str]]:

    found: Dict[str, Set[str]] = {}

    if not bundle_text:
        return {}

    for match in STORE_ID_PATTERN.finditer(bundle_text):

        key = match.group(1)
        value = match.group(2)

        if not value:
            continue

        found.setdefault(key, set()).add(value)

    return {k: sorted(v) for k, v in found.items()}


# ---------------------------------------------------------
# GraphQL Ops
# ---------------------------------------------------------

GRAPHQL_OPERATION_PATTERN = re.compile(
    r"""\b(query|mutation)\s+([A-Za-z_][A-Za-z0-9_]{1,80})""",
)


def parse_bundle_for_graphql_operations(bundle_text: str) -> List[str]:

    discovered = set()

    if not bundle_text:
        return []

    for match in GRAPHQL_OPERATION_PATTERN.finditer(bundle_text):
        discovered.add(match.group(2))

    return sorted(discovered)


# ---------------------------------------------------------
# Dynamic Chunks
# ---------------------------------------------------------

DYNAMIC_IMPORT_PATTERN = re.compile(r"""import\(["']([^"']+\.js)""")
WEBPACK_CHUNK_PATTERN = re.compile(r"""webpack.*?["']([^"']+\.js)""")


def parse_bundle_for_dynamic_chunks(bundle_text: str) -> List[str]:

    discovered = set()

    for pattern in (DYNAMIC_IMPORT_PATTERN, WEBPACK_CHUNK_PATTERN):

        for match in pattern.finditer(bundle_text):
            discovered.add(match.group(1))

    return sorted(discovered)


# ---------------------------------------------------------
# Metadata Aggregation
# ---------------------------------------------------------

def parse_bundle_metadata(bundle_text: str) -> Dict[str, object]:

    return {
        "endpoints": parse_bundle_for_endpoints(bundle_text),
        "provider_hints": parse_bundle_for_provider_hints(bundle_text),
        "image_urls": parse_bundle_for_image_urls(bundle_text),
        "store_ids": parse_bundle_for_store_ids(bundle_text),
        "graphql_operations": parse_bundle_for_graphql_operations(bundle_text),
        "dynamic_chunks": parse_bundle_for_dynamic_chunks(bundle_text),
    }


def parse_multiple_bundles(bundles: Dict[str, str]) -> Dict[str, object]:

    merged_endpoints: Set[str] = set()
    merged_provider_hints: Set[str] = set()
    merged_image_urls: Set[str] = set()
    merged_graphql_ops: Set[str] = set()
    merged_dynamic_chunks: Set[str] = set()
    merged_store_ids: Dict[str, Set[str]] = {}
    by_bundle: Dict[str, Dict[str, object]] = {}

    for bundle_url, bundle_text in bundles.items():

        try:
            meta = parse_bundle_metadata(bundle_text)
            by_bundle[bundle_url] = meta

            merged_endpoints.update(meta["endpoints"])
            merged_provider_hints.update(meta["provider_hints"])
            merged_image_urls.update(meta["image_urls"])
            merged_graphql_ops.update(meta["graphql_operations"])
            merged_dynamic_chunks.update(meta["dynamic_chunks"])

            for key, values in meta["store_ids"].items():
                merged_store_ids.setdefault(key, set()).update(values)

        except Exception as exc:
            logger.debug("js_bundle_parser_failed url=%s error=%s", bundle_url, exc)

    return {
        "endpoints": sorted(merged_endpoints)[:MAX_TOTAL_ENDPOINTS],
        "provider_hints": sorted(merged_provider_hints),
        "image_urls": sorted(merged_image_urls)[:MAX_IMAGE_URLS_PER_BUNDLE],
        "store_ids": {k: sorted(v) for k, v in merged_store_ids.items()},
        "graphql_operations": sorted(merged_graphql_ops),
        "dynamic_chunks": sorted(merged_dynamic_chunks),
        "by_bundle": by_bundle,
    }