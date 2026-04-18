from __future__ import annotations

import logging
from typing import Dict, List

from app.services.discovery.nominatim_client import search_place


logger = logging.getLogger(__name__)


def geocode_records(records: List[Dict]) -> List[Dict]:
    result = []

    for record in records:
        if record.get("lat") is not None and record.get("lng") is not None:
            result.append(record)
            continue

        name = record.get("name", "")
        address = record.get("address", "")
        query = " ".join(p for p in [name, address] if p).strip()

        if not query:
            result.append(record)
            continue

        try:
            geo = search_place(query=query)
            if geo and geo.get("lat") and geo.get("lon"):
                record = dict(record)
                record["lat"] = float(geo["lat"])
                record["lng"] = float(geo["lon"])
                record["confidence"] = 0.75
                logger.debug("health_geocoded name=%s lat=%s lng=%s", name, record["lat"], record["lng"])
            else:
                logger.debug("health_geocode_miss name=%s query=%s", name, query)
        except Exception as exc:
            logger.debug("health_geocode_error name=%s error=%s", name, exc)

        result.append(record)

    return result
