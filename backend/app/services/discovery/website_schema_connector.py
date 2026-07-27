from __future__ import annotations

# DEPRECATED / UNUSED: written during an earlier discovery-source phase and
# never wired into app.services.discovery.pipeline_v2, which is the discovery
# path app/scheduler.py actually calls. A grep across the entire backend/
# tree found zero imports of app.services.discovery.website_schema_connector
# or fetch_website_schema from anywhere.
# Kept here for reference only — not wired up. Safe to delete if no longer needed.

import logging
from typing import Any, Dict, Optional

from app.services.network.http_fetcher import fetch
from app.services.schema.schema_extractor import extract_schema
from app.services.schema.schema_parser import parse_schema


logger = logging.getLogger(__name__)


def fetch_website_schema(
    website: str,
) -> Optional[Dict[str, Any]]:
    """
    Fetch schema.org structured data from a website.
    """

    try:

        response = fetch(website)

        if response.status_code != 200:
            return None

        html = response.text

        raw_schema = extract_schema(html)

        if not raw_schema:
            return None

        parsed = parse_schema(raw_schema)

        return parsed

    except Exception as exc:

        logger.debug(
            "website_schema_fetch_failed website=%s error=%s",
            website,
            exc,
        )

        return None