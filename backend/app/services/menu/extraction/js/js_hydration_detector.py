from __future__ import annotations

import json
import logging
import re
import html as html_lib
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# Patterns
# ---------------------------------------------------------

HYDRATION_PATTERNS = [

    # Next.js
    r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',

    # Nuxt
    r'window\.__NUXT__\s*=\s*(\{.*?\});',

    # Apollo
    r'window\.__APOLLO_STATE__\s*=\s*(\{.*?\});',

    # Redux
    r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});',

    # Shopify
    r'window\.ShopifyAnalytics\.meta\s*=\s*(\{.*?\});',

    # Generic
    r'window\.__DATA__\s*=\s*(\{.*?\});',
    r'window\.__APP_STATE__\s*=\s*(\{.*?\});',

    # Astro
    r'<astro-island[^>]*props="([^"]+)"',

    # JSON script blobs
    r'<script[^>]*type="application/json"[^>]*>(.*?)</script>',
]


MAX_PAYLOAD_SIZE = 5_000_000


# ---------------------------------------------------------
# JSON Recovery
# ---------------------------------------------------------

def _safe_json_load(raw: str) -> Optional[Any]:

    if not raw:
        return None

    if len(raw) > MAX_PAYLOAD_SIZE:
        return None

    raw = raw.strip()

    # decode HTML entities
    raw = html_lib.unescape(raw)

    try:
        return json.loads(raw)
    except Exception:
        pass

    # attempt fixes
    try:
        raw = raw.rstrip(";")
        return json.loads(raw)
    except Exception:
        pass

    # last attempt: extract JSON substring
    try:
        start = raw.find("{")
        end = raw.rfind("}")

        if start != -1 and end != -1:
            return json.loads(raw[start:end + 1])
    except Exception:
        pass

    return None


# ---------------------------------------------------------
# Extraction
# ---------------------------------------------------------

def _extract_all_payloads(html: str) -> List[Any]:

    payloads: List[Any] = []

    for pattern in HYDRATION_PATTERNS:

        try:

            for match in re.finditer(
                pattern,
                html,
                re.DOTALL | re.IGNORECASE,
            ):

                raw = match.group(1)

                parsed = _safe_json_load(raw)

                if parsed:
                    payloads.append(parsed)

        except Exception as exc:

            logger.debug(
                "hydration_pattern_failed pattern=%s error=%s",
                pattern[:30],
                exc,
            )

    return payloads


# ---------------------------------------------------------
# Payload Quality Scoring
# ---------------------------------------------------------

def _score_payload(payload: Any) -> int:

    if not isinstance(payload, dict):
        return 0

    score = 0

    keys = {str(k).lower() for k in payload.keys()}

    if "menu" in keys or "menus" in keys:
        score += 25

    if "items" in keys or "products" in keys:
        score += 20

    if "categories" in keys:
        score += 15

    if "price" in keys:
        score += 10

    if len(payload) > 5:
        score += 5

    return score


# ---------------------------------------------------------
# Public API
# ---------------------------------------------------------

def detect_hydration_state(html: str) -> Dict[str, Any]:

    if not html:
        return {}

    payloads = _extract_all_payloads(html)

    if not payloads:
        return {}

    # pick best payload
    best_payload = max(payloads, key=_score_payload)

    logger.info(
        "hydration_detected payloads=%s best_score=%s",
        len(payloads),
        _score_payload(best_payload),
    )

    return {
        "type": "hydration",
        "raw": best_payload,
    }