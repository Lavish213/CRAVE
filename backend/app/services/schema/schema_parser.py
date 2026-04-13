from __future__ import annotations

import logging
from typing import Dict, List, Any


logger = logging.getLogger(__name__)


def parse_schema(
    schemas: List[Dict[str, Any]],
) -> List[Dict]:

    results: List[Dict] = []

    for schema in schemas:

        try:

            schema_type = schema.get("@type")

            if not schema_type:
                continue

            results.append(schema)

        except Exception as exc:

            logger.debug(
                "schema_parser_failed error=%s",
                exc,
            )

    return results