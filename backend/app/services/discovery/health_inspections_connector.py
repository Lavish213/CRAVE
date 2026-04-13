from __future__ import annotations

import logging
import hashlib
from typing import Dict, Iterable, List


logger = logging.getLogger(__name__)


SOURCE_NAME = "health_inspections"


def _build_external_id(row: Dict) -> str:
    """
    Create a stable ID so the same facility
    is not inserted repeatedly across runs.
    """

    facility_id = row.get("facility_id")
    name = row.get("facility_name")
    address = row.get("address")

    base = f"{facility_id}:{name}:{address}"

    digest = hashlib.sha1(base.encode()).hexdigest()

    return f"health:{digest}"


class HealthInspectionsConnector:
    """
    Converts health inspection datasets into discovery records.
    """

    def parse(
        self,
        rows: Iterable[Dict],
    ) -> List[Dict]:

        results: List[Dict] = []

        for row in rows:

            try:

                name = row.get("facility_name")
                address = row.get("address")

                if not name or not address:
                    continue

                lat = row.get("lat") or row.get("latitude")
                lon = row.get("lon") or row.get("longitude")

                record = {
                    "external_id": _build_external_id(row),

                    "name": name,
                    "address": address,

                    "lat": lat,
                    "lon": lon,

                    "phone": row.get("phone"),
                    "website": None,

                    "city_id": row.get("city_id"),
                    "category_id": None,

                    "source": SOURCE_NAME,

                    "confidence": 0.9,

                    "raw_payload": row,
                }

                results.append(record)

            except Exception as exc:

                logger.debug(
                    "health_inspection_parse_failed error=%s",
                    exc,
                )

        logger.info(
            "health_inspections_parsed count=%s",
            len(results),
        )

        return results