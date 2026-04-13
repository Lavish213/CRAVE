from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set


logger = logging.getLogger(__name__)


MAX_ENDPOINTS_EVALUATED = 200


# ---------------------------------------------------------
# Signals
# ---------------------------------------------------------

MENU_KEYWORDS = {
    "menu",
    "menus",
    "item",
    "items",
    "product",
    "products",
    "catalog",
    "category",
    "categories",
    "section",
    "sections",
    "modifier",
    "modifiers",
}

API_KEYWORDS = {
    "api",
    "graphql",
    "v1",
    "v2",
    "v3",
}

PROVIDER_HINTS = {
    "toast",
    "clover",
    "chownow",
    "popmenu",
    "olo",
    "square",
}

NEGATIVE_HINTS = {
    "analytics",
    "tracking",
    "pixel",
    "metrics",
    "telemetry",
    "ads",
    "facebook",
    "segment",
    "cdn",
    "static",
}


PRICE_KEYS = {"price", "amount", "displayprice", "unitprice"}
NAME_KEYS = {"name", "title", "label"}
CATEGORY_KEYS = {"category", "section", "group", "menu"}


# ---------------------------------------------------------
# URL Scoring
# ---------------------------------------------------------

def _score_url(url: str) -> int:

    lower = url.lower()
    score = 0

    # menu relevance
    for word in MENU_KEYWORDS:
        if word in lower:
            score += 12

    # api structure
    for word in API_KEYWORDS:
        if word in lower:
            score += 4

    # providers
    for provider in PROVIDER_HINTS:
        if provider in lower:
            score += 18

    # strong boost for graphql
    if "graphql" in lower:
        score += 25

    # penalties
    for bad in NEGATIVE_HINTS:
        if bad in lower:
            score -= 25

    # short endpoints often better
    if len(lower) < 120:
        score += 5

    return score


# ---------------------------------------------------------
# Payload Scoring
# ---------------------------------------------------------

def _score_payload(payload: Dict) -> int:

    if not isinstance(payload, dict):
        return 0

    keys = {str(k).lower() for k in payload.keys()}
    score = 0

    if keys & NAME_KEYS:
        score += 8

    if keys & PRICE_KEYS:
        score += 12

    if keys & CATEGORY_KEYS:
        score += 8

    if "items" in keys or "products" in keys:
        score += 18

    if "menus" in keys:
        score += 20

    # deeper nested signals
    for value in payload.values():

        if isinstance(value, list) and value:

            if isinstance(value[0], dict):

                inner_keys = {str(k).lower() for k in value[0].keys()}

                if inner_keys & PRICE_KEYS:
                    score += 10

                if inner_keys & NAME_KEYS:
                    score += 8

    return score


def _score_sample(sample: Optional[Dict]) -> int:

    if not sample:
        return -5  # penalize empty sample

    try:

        if isinstance(sample, dict):
            return _score_payload(sample)

        if isinstance(sample, list):

            if not sample:
                return -5

            if isinstance(sample[0], dict):
                return _score_payload(sample[0])

    except Exception:
        return -5

    return 0


# ---------------------------------------------------------
# Public API
# ---------------------------------------------------------

def rank_js_endpoints(
    endpoints: List[Dict],
) -> List[Dict]:
    """
    Rank JS-discovered endpoints.

    Input:
        {
            "url": str,
            "method": "GET" | "POST",
            "sample": optional json payload,
        }
    """

    if not endpoints:
        return []

    ranked: List[Dict] = []
    seen_urls: Set[str] = set()

    for endpoint in endpoints[:MAX_ENDPOINTS_EVALUATED]:

        url = endpoint.get("url")

        if not url:
            continue

        if url in seen_urls:
            continue

        seen_urls.add(url)

        method = endpoint.get("method", "GET")
        sample = endpoint.get("sample")

        score = 0

        score += _score_url(url)
        score += _score_sample(sample)

        # POST often indicates real API
        if method == "POST":
            score += 6

        ranked.append(
            {
                "url": url,
                "method": method,
                "sample": sample,
                "score": score,
            }
        )

    ranked.sort(key=lambda x: x["score"], reverse=True)

    logger.debug(
        "js_endpoint_ranked count=%s top_score=%s",
        len(ranked),
        ranked[0]["score"] if ranked else None,
    )

    return ranked