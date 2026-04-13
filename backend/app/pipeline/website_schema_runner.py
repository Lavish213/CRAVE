from __future__ import annotations

import logging
from typing import Dict, Iterable, List

from app.services.schema.schema_extractor import extract_schema
from app.services.schema.schema_parser import parse_schema
from app.services.schema.schema_normalizer import normalize_schema

from app.services.network.http_fetcher import fetch


logger = logging.getLogger(__name__)


class WebsiteSchemaRunner:
    """
    Extract schema.org structured data from restaurant websites.
    """

    def run(
        self,
        entities: Iterable[Dict],
    ) -> List[Dict]:

        results: List[Dict] = []

        for entity in entities:

            website = entity.get("website")

            if not website:
                results.append(entity)
                continue

            try:

                response = fetch(website)

                if response.status_code != 200:
                    results.append(entity)
                    continue

                html = response.text

                raw_schema = extract_schema(html)

                parsed = parse_schema(raw_schema)

                normalized = normalize_schema(parsed)

                if normalized:
                    entity["schema"] = normalized

            except Exception as exc:

                logger.debug(
                    "schema_extraction_failed website=%s error=%s",
                    website,
                    exc,
                )

            results.append(entity)

        logger.info(
            "website_schema_runner_complete entities=%s",
            len(results),
        )

        return results