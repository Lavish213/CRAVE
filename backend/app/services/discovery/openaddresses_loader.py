from __future__ import annotations

import logging
from typing import Dict, Iterable, List

from app.services.entity.normalize_address import normalize_address


logger = logging.getLogger(__name__)


class OpenAddressesLoader:
    """
    Loads address datasets from OpenAddresses
    and converts them into normalized ingest records.
    """

    def load(
        self,
        rows: Iterable[Dict],
    ) -> List[Dict]:

        results: List[Dict] = []

        for row in rows:

            try:

                address = row.get("address")

                lat = row.get("lat")
                lon = row.get("lon")

                if not address:
                    continue

                if lat is None or lon is None:
                    continue

                try:
                    lat = float(lat)
                    lon = float(lon)
                except Exception:
                    continue

                normalized_address = normalize_address(address)

                record = {
                    "external_id": row.get("id") or row.get("uuid"),
                    "name": None,
                    "address": address,
                    "normalized_address": normalized_address,
                    "lat": lat,
                    "lon": lon,
                    "phone": None,
                    "website": None,
                    "source": "openaddresses",
                    "raw_payload": row,
                }

                results.append(record)

            except Exception as exc:

                logger.debug(
                    "openaddresses_parse_failed error=%s",
                    exc,
                )

        logger.info(
            "openaddresses_loaded count=%s",
            len(results),
        )

        return results