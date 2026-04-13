from __future__ import annotations

import logging
from typing import Dict, Optional

from app.services.network.http_fetcher import fetch


logger = logging.getLogger(__name__)


NOMINATIM_URL = "https://nominatim.openstreetmap.org"


def reverse_geocode(
    *,
    lat: float,
    lon: float,
) -> Optional[Dict]:

    url = f"{NOMINATIM_URL}/reverse"

    params = {
        "lat": lat,
        "lon": lon,
        "format": "jsonv2",
        "addressdetails": 1,
    }

    try:

        response = fetch(
            url,
            method="GET",
            params=params,
            headers={
                "User-Agent": "restaurant-discovery-engine"
            },
        )

        if response.status_code != 200:
            return None

        data = response.json()

    except Exception as exc:

        logger.debug(
            "nominatim_reverse_failed lat=%s lon=%s error=%s",
            lat,
            lon,
            exc,
        )

        return None

    return {
        "display_name": data.get("display_name"),
        "address": data.get("address"),
        "osm_id": data.get("osm_id"),
        "osm_type": data.get("osm_type"),
    }


def search_place(
    *,
    query: str,
) -> Optional[Dict]:

    url = f"{NOMINATIM_URL}/search"

    params = {
        "q": query,
        "format": "jsonv2",
        "limit": 1,
    }

    try:

        response = fetch(
            url,
            method="GET",
            params=params,
            headers={
                "User-Agent": "restaurant-discovery-engine"
            },
        )

        if response.status_code != 200:
            return None

        data = response.json()

        if not data:
            return None

        result = data[0]

    except Exception as exc:

        logger.debug(
            "nominatim_search_failed query=%s error=%s",
            query,
            exc,
        )

        return None

    return {
        "name": result.get("display_name"),
        "lat": result.get("lat"),
        "lon": result.get("lon"),
        "osm_id": result.get("osm_id"),
        "osm_type": result.get("osm_type"),
    }