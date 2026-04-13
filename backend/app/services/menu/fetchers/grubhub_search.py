from __future__ import annotations

import logging
from typing import List, Dict, Optional
from urllib.parse import quote_plus

from app.services.network.http_fetcher import fetch


logger = logging.getLogger(__name__)


# =========================================================
# CONFIG
# =========================================================

GRUBHUB_SEARCH_URL = "https://www.grubhub.com/search"
MAX_RESULTS = 10


# =========================================================
# MAIN ENTRY
# =========================================================

def search_grubhub(
    *,
    name: str,
    lat: Optional[float],
    lng: Optional[float],
) -> List[Dict]:
    """
    🔥 PRODUCTION GRUBHUB SEARCH DISCOVERY

    Returns normalized candidates:
    [
        {
            "id": str,
            "name": str,
            "lat": float,
            "lng": float,
            "url": str,
        }
    ]
    """

    if not name:
        return []

    query = _build_query(name, lat, lng)
    url = f"{GRUBHUB_SEARCH_URL}/{quote_plus(query)}"

    try:
        response = fetch(
            url,
            method="GET",
            mode="document",
            referer="https://www.grubhub.com/",
        )

        html = response.text or ""

    except Exception as exc:
        logger.warning(
            "grubhub_search_failed query=%s error=%s",
            query,
            exc,
        )
        return []

    return _parse_search_results(html)


# =========================================================
# QUERY BUILDER
# =========================================================

def _build_query(name: str, lat: Optional[float], lng: Optional[float]) -> str:

    base = name.strip()

    if lat is not None and lng is not None:
        return f"{base} {lat},{lng}"

    return base


# =========================================================
# PARSER (LIGHTWEIGHT HTML PARSE)
# =========================================================

def _parse_search_results(html: str) -> List[Dict]:

    if not html:
        return []

    results: List[Dict] = []

    # 🔥 Grubhub embeds JSON in page → fastest path
    import re
    import json

    matches = re.findall(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', html)

    for match in matches:
        try:
            data = json.loads(match)

            restaurants = (
                data.get("searchResults", {})
                .get("results", [])
            )

            for r in restaurants[:MAX_RESULTS]:

                item = _convert_restaurant(r)

                if item:
                    results.append(item)

        except Exception:
            continue

    return results


# =========================================================
# NORMALIZER
# =========================================================

def _convert_restaurant(r: Dict) -> Optional[Dict]:

    try:
        name = r.get("name")

        lat = r.get("latitude")
        lng = r.get("longitude")

        url_path = r.get("url")

        if not name or not url_path:
            return None

        return {
            "id": str(r.get("restaurant_id") or r.get("id")),
            "name": name,
            "lat": lat,
            "lng": lng,
            "url": f"https://www.grubhub.com{url_path}",
        }

    except Exception:
        return None