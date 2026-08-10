from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

from app.services.network.http_fetcher import fetch


logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _clean_string(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = value.strip()
    return value or None


def _normalize_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None

    phone = re.sub(r"[^\d+]", "", phone)

    if len(phone) < 7:
        return None

    return phone


def _normalize_website(url: Optional[str]) -> Optional[str]:
    if not url:
        return None

    url = url.strip()

    if not url.startswith("http"):
        url = "https://" + url

    return url


# ---------------------------------------------------------
# Address Builder
# ---------------------------------------------------------

def _build_address(tags: Dict) -> Optional[str]:

    full = tags.get("addr:full")

    if full:
        return full

    number = tags.get("addr:housenumber")
    street = tags.get("addr:street")
    city = tags.get("addr:city")

    parts = [number, street, city]

    address = " ".join(p for p in parts if p)

    return address or None


# ---------------------------------------------------------
# Category Detection
# ---------------------------------------------------------

def _category_hint(tags: Dict) -> Optional[str]:

    amenity = tags.get("amenity")

    if amenity:
        return amenity

    shop = tags.get("shop")

    if shop:
        return shop

    cuisine = tags.get("cuisine")

    if cuisine:
        return cuisine.split(";")[0]

    return None


# ---------------------------------------------------------
# OSM Fetch
# ---------------------------------------------------------

def fetch_osm_pois(
    *,
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
) -> List[Dict]:

    query = f"""
    [out:json][timeout:25];
    (
      node["amenity"~"restaurant|fast_food|cafe|bar|pub|food_court|ice_cream|biergarten"]({lat_min},{lon_min},{lat_max},{lon_max});
      way["amenity"~"restaurant|fast_food|cafe|bar|pub|food_court|ice_cream|biergarten"]({lat_min},{lon_min},{lat_max},{lon_max});
      relation["amenity"~"restaurant|fast_food|cafe|bar|pub|food_court|ice_cream|biergarten"]({lat_min},{lon_min},{lat_max},{lon_max});

      node["shop"~"bakery|deli"]({lat_min},{lon_min},{lat_max},{lon_max});
      way["shop"~"bakery|deli"]({lat_min},{lon_min},{lat_max},{lon_max});
    );
    out center tags;
    """

    try:

        response = fetch(
            OVERPASS_URL,
            method="POST",
            data=query,
        )

        if response.status_code != 200:

            logger.warning(
                "osm_fetch_bad_status code=%s",
                response.status_code,
            )

            return []

        data = response.json()

    except Exception as exc:

        logger.debug(
            "osm_fetch_failed error=%s",
            exc,
        )

        return []

    results: List[Dict] = []

    for el in data.get("elements", []):

        tags = el.get("tags", {}) or {}

        name = _clean_string(tags.get("name"))

        if not name:
            continue

        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")

        if lat is None or lon is None:
            continue

        address = _build_address(tags)

        phone = _normalize_phone(tags.get("phone"))
        website = _normalize_website(tags.get("website"))

        category = _category_hint(tags)

        record = {

            "external_id": f"osm:{el.get('type')}:{el.get('id')}",

            "name": name,

            "address": address,

            "lat": float(lat),
            "lon": float(lon),

            "phone": phone,
            "website": website,

            "category_hint": category,

            "source": "osm",

            # Was 0.6 — below promotion_orchestrator_v2.MIN_CONFIDENCE_THRESHOLD
            # (0.72), and OSM candidates never accumulate confidence the way
            # user-corroboration sources do (candidate_store_v2's max() merge
            # for automated sources, since a re-scan by the same source isn't
            # new evidence). That meant every OSM candidate was permanently
            # stuck in discovery_candidates, never promoted and never
            # backfilling Place.website onto a matched existing place —
            # silently defeating the whole OSM pipeline regardless of data
            # quality. 0.75 matches the confidence already given to
            # comparably-sourced automated data elsewhere in this package
            # (health_normalizer/health_geocoder use 0.75 for geocoded
            # records), and only governs backfilling missing fields onto an
            # already-matched Place or creating a new one through the same
            # entity-matching gate every other source goes through — it does
            # not bypass any dedup/matching logic.
            "confidence": 0.75,

            "raw_payload": tags,
        }

        results.append(record)

    logger.info(
        "osm_pois_fetched count=%s",
        len(results),
    )

    return results
