from __future__ import annotations

import logging
from typing import Dict, Iterable, List

from app.services.discovery.website_discovery_connector import discover_websites


logger = logging.getLogger(__name__)


class WebsiteDiscoveryRunner:
    """
    Attempts to discover official websites
    for restaurant entities.
    """

    def run(
        self,
        entities: Iterable[Dict],
    ) -> List[Dict]:

        updated_entities: List[Dict] = []

        for entity in entities:

            try:

                website = discover_websites(
                    name=entity.get("name"),
                    address=entity.get("address"),
                    lat=entity.get("lat"),
                    lon=entity.get("lon"),
                )

                if website:
                    entity["website"] = website

                updated_entities.append(entity)

            except Exception as exc:

                logger.debug(
                    "website_discovery_failed name=%s error=%s",
                    entity.get("name"),
                    exc,
                )

        logger.info(
            "website_discovery_complete entities=%s",
            len(updated_entities),
        )

        return updated_entities