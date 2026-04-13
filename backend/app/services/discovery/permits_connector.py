from __future__ import annotations

import logging
from typing import Dict, Iterable, List


logger = logging.getLogger(__name__)


class PermitsConnector:
    """
    Converts permit datasets into discovery records.
    """

    def parse(
        self,
        rows: Iterable[Dict],
    ) -> List[Dict]:

        results: List[Dict] = []

        for row in rows:

            try:

                record = {
                    "name": row.get("business_name"),
                    "address": row.get("address"),
                    "lat": row.get("lat"),
                    "lon": row.get("lon"),
                    "phone": row.get("phone"),
                    "website": row.get("website"),
                    "source": "permits",
                    "raw": row,
                }

                results.append(record)

            except Exception as exc:

                logger.debug(
                    "permit_parse_failed error=%s",
                    exc,
                )

        logger.info(
            "permits_parsed count=%s",
            len(results),
        )

        return results