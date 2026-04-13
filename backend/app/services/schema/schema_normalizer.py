from __future__ import annotations

import logging
from typing import Dict, List


logger = logging.getLogger(__name__)


def normalize_schema(
    schemas: List[Dict],
) -> List[Dict]:

    normalized: List[Dict] = []

    for schema in schemas:

        try:

            entry = {}

            entry["type"] = schema.get("@type")

            entry["name"] = schema.get("name")

            entry["url"] = schema.get("url")

            entry["telephone"] = schema.get("telephone")

            address = schema.get("address")

            if isinstance(address, dict):
                entry["address"] = address.get("streetAddress")

            menu = schema.get("hasMenu") or schema.get("menu")

            if menu:
                entry["menu"] = menu

            normalized.append(entry)

        except Exception as exc:

            logger.debug(
                "schema_normalize_failed error=%s",
                exc,
            )

    return normalized