from __future__ import annotations

import logging
from typing import Dict, List, Set
from urllib.parse import parse_qsl, urljoin, urlparse, urlunparse


logger = logging.getLogger(__name__)


MAX_NORMALIZED_ENDPOINTS = 100


POSITIVE_SIGNALS = (
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

NEGATIVE_SIGNALS = (
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
    "beacon",
    "pixel",
    "captcha",
    "csrf",
    "refresh-token",
    "signin",
    "signup",
    "account",
    "profile",
)


ALLOWED_SCHEMES = ("http", "https")

COMMON_API_PREFIXES = (
    "/api/",
    "/graphql",
    "/menu",
    "/menus",
    "/products",
    "/product",
    "/items",
    "/item",
    "/catalog",
    "/category",
    "/categories",
    "/food",
    "/order",
    "/ordering",
)

TRAILING_JUNK = (",", ";", ")", "]", "}", ".")


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _strip_trailing_junk(value: str) -> str:
    cleaned = value.strip()

    while cleaned and cleaned[-1] in TRAILING_JUNK:
        cleaned = cleaned[:-1].rstrip()

    return cleaned


def _drop_fragment(url: str) -> str:
    parsed = urlparse(url)

    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            "",
        )
    )


def _filter_query_params(url: str) -> str:
    parsed = urlparse(url)

    if not parsed.query:
        return url

    pairs = parse_qsl(parsed.query, keep_blank_values=True)

    cleaned = []

    for k, v in pairs:

        lk = k.lower()

        # remove junk params
        if any(bad in lk for bad in ("token", "auth", "session", "ts", "cache", "sig")):
            continue

        cleaned.append((k, v))

    cleaned.sort()

    new_query = "&".join(f"{k}={v}" if v else k for k, v in cleaned)

    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            "",
        )
    )


def _normalize_absolute_url(url: str) -> str:
    url = _drop_fragment(url)
    url = _filter_query_params(url)

    parsed = urlparse(url)

    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            parsed.params,
            parsed.query,
            "",
        )
    )


def _normalize_relative_url(url: str) -> str:
    return _strip_trailing_junk(url)


def _looks_like_endpoint_candidate(value: str) -> bool:
    lowered = value.lower()

    if len(lowered) < 4:
        return False

    if lowered.startswith("//"):
        return True

    if lowered.startswith("http://") or lowered.startswith("https://"):
        return True

    return lowered.startswith(COMMON_API_PREFIXES)


def _contains_positive_signal(value: str) -> bool:
    lowered = value.lower()

    if "graphql" in lowered:
        return True  # force allow GraphQL

    return any(token in lowered for token in POSITIVE_SIGNALS)


def _contains_negative_signal(value: str) -> bool:
    lowered = value.lower()
    return any(token in lowered for token in NEGATIVE_SIGNALS)


def _normalize_endpoint(raw_endpoint: str, base_url: str) -> str | None:
    if not raw_endpoint:
        return None

    endpoint = _strip_trailing_junk(raw_endpoint)

    if not endpoint:
        return None

    if not _looks_like_endpoint_candidate(endpoint):
        return None

    if endpoint.startswith("//"):
        endpoint = f"https:{endpoint}"

    parsed = urlparse(endpoint)

    if parsed.scheme in ALLOWED_SCHEMES and parsed.netloc:
        return _normalize_absolute_url(endpoint)

    if endpoint.startswith("/"):
        absolute = urljoin(base_url, endpoint)
        return _normalize_absolute_url(absolute)

    return None


# ---------------------------------------------------------
# Main Normalization
# ---------------------------------------------------------

def normalize_endpoints(
    endpoints: List[str],
    base_url: str,
) -> List[str]:

    normalized: Set[str] = set()

    if not endpoints or not base_url:
        return []

    for endpoint in endpoints:

        if len(normalized) >= MAX_NORMALIZED_ENDPOINTS:
            break

        absolute = _normalize_endpoint(endpoint, base_url)

        if not absolute:
            continue

        if _contains_negative_signal(absolute):
            continue

        if not _contains_positive_signal(absolute):
            continue

        if len(absolute) > 200:
            continue

        normalized.add(absolute)

    results = sorted(normalized)

    logger.debug(
        "js_endpoint_scanner_normalized count=%s base_url=%s",
        len(results),
        base_url,
    )

    return results[:MAX_NORMALIZED_ENDPOINTS]


# ---------------------------------------------------------
# Bundle Metadata Scanner
# ---------------------------------------------------------

def scan_parsed_bundle_metadata(
    parsed_bundle_metadata: Dict[str, object],
    base_url: str,
) -> Dict[str, object]:

    endpoints = parsed_bundle_metadata.get("endpoints", [])
    provider_hints = parsed_bundle_metadata.get("provider_hints", [])
    image_urls = parsed_bundle_metadata.get("image_urls", [])
    store_ids = parsed_bundle_metadata.get("store_ids", {})
    graphql_operations = parsed_bundle_metadata.get("graphql_operations", [])
    dynamic_chunks = parsed_bundle_metadata.get("dynamic_chunks", [])

    if not isinstance(endpoints, list):
        endpoints = []

    normalized_endpoints = normalize_endpoints(endpoints, base_url)

    clean_provider_hints = sorted(
        {
            str(v).strip().lower()
            for v in provider_hints
            if str(v).strip()
        }
    )

    clean_image_urls = sorted(
        {
            _normalize_endpoint(v, base_url) or _normalize_relative_url(v)
            for v in image_urls
            if str(v).strip()
        }
    )

    clean_store_ids: Dict[str, List[str]] = {}

    for key, values in store_ids.items():

        if not isinstance(values, list):
            continue

        clean_vals = sorted(
            {
                str(v).strip()
                for v in values
                if str(v).strip() and len(str(v)) < 120
            }
        )

        if clean_vals:
            clean_store_ids[str(key).strip()] = clean_vals

    clean_graphql_operations = sorted(
        {
            str(v).strip()
            for v in graphql_operations
            if str(v).strip()
        }
    )

    clean_dynamic_chunks = sorted(
        {
            str(v).strip()
            for v in dynamic_chunks
            if str(v).strip()
        }
    )

    result = {
        "endpoints": normalized_endpoints,
        "provider_hints": clean_provider_hints,
        "image_urls": clean_image_urls,
        "store_ids": clean_store_ids,
        "graphql_operations": clean_graphql_operations,
        "dynamic_chunks": clean_dynamic_chunks,
    }

    logger.debug(
        "js_endpoint_scanner_complete endpoints=%s providers=%s graphql_ops=%s",
        len(result["endpoints"]),
        len(result["provider_hints"]),
        len(result["graphql_operations"]),
    )

    return result