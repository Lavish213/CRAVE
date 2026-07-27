from __future__ import annotations

import logging
from typing import Dict, Optional

from app.config.settings import settings
from app.services.network.http_fetcher import fetch


logger = logging.getLogger(__name__)


NOMINATIM_URL = "https://nominatim.openstreetmap.org"

# Rate limiting: every call to fetch() passes through
# app.services.network.domain_rate_limiter.wait_for_domain(), which enforces
# a minimum 2.0s gap between requests to any domain not given a faster
# explicit rule (see domain_rate_limiter._DOMAIN_RULES) — nominatim.
# openstreetmap.org has no override, so it gets that 2.0s floor. That
# already satisfies (and is stricter than) Nominatim's documented "max 1
# request per second" policy, so no additional per-call throttling is
# needed here. What Nominatim's policy also requires — and what was
# actually missing — is an identifying User-Agent with real contact info;
# see _user_agent() below.


def _user_agent() -> str:
    contact = (settings.nominatim_contact or "").strip()
    if contact:
        return f"CraveApp/1.0 ({contact})"
    # No contact configured — still identify the app, but this does not
    # meet Nominatim's policy and may get silently blocked. Set
    # NOMINATIM_CONTACT in the environment (see app/config/settings.py).
    logger.warning(
        "nominatim_contact_unset using non-compliant User-Agent — "
        "set NOMINATIM_CONTACT to an email or contact URL"
    )
    return "CraveApp/1.0 (contact not configured)"


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
                "User-Agent": _user_agent()
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
                "User-Agent": _user_agent()
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