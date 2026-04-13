from __future__ import annotations

import json
import logging
import re
from typing import List, Dict, Any


logger = logging.getLogger(__name__)


SCRIPT_RE = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
    re.I | re.S,
)


def extract_schema(html: str) -> List[Dict[str, Any]]:

    schemas: List[Dict[str, Any]] = []

    if not html:
        return schemas

    matches = SCRIPT_RE.findall(html)

    for block in matches:

        try:

            data = json.loads(block)

            if isinstance(data, list):
                schemas.extend(data)
            else:
                schemas.append(data)

        except Exception as exc:

            logger.debug(
                "schema_parse_failed error=%s",
                exc,
            )

    return schemas