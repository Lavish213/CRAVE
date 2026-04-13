from __future__ import annotations

import logging
from typing import Dict, List
from urllib.parse import urlparse


logger = logging.getLogger(__name__)


MAX_DUPLICATE_CLUSTER = 5


class ImageDeduper:
    """
    Removes duplicate or near-duplicate image candidates.

    Deduplication layers
    --------------------
    - exact URL duplicates
    - normalized URL duplicates (strip params)
    - filename duplicates
    """

    def dedupe(
        self,
        *,
        place,
        candidates: List[dict],
    ) -> List[dict]:

        if not candidates:
            return []

        place_id = getattr(place, "id", None)

        url_seen = set()
        filename_seen = set()

        deduped: List[dict] = []

        for candidate in candidates:

            try:

                url = candidate.get("url")

                if not url:
                    continue

                normalized_url = self._normalize_url(url)

                filename = self._filename(url)

                if normalized_url in url_seen:
                    continue

                if filename in filename_seen:
                    continue

                url_seen.add(normalized_url)

                if filename:
                    filename_seen.add(filename)

                deduped.append(candidate)

            except Exception as exc:

                logger.debug(
                    "image_dedupe_failed place_id=%s error=%s",
                    place_id,
                    exc,
                )

        logger.info(
            "image_dedupe_complete place_id=%s input=%s output=%s",
            place_id,
            len(candidates),
            len(deduped),
        )

        return deduped

    # ---------------------------------------------------------
    # URL normalization
    # ---------------------------------------------------------

    def _normalize_url(
        self,
        url: str,
    ) -> str:

        try:

            parsed = urlparse(url)

            normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

            return normalized.lower()

        except Exception:

            return url.lower()

    def _filename(
        self,
        url: str,
    ) -> str | None:

        try:

            path = urlparse(url).path

            if not path:
                return None

            filename = path.split("/")[-1]

            if not filename:
                return None

            return filename.lower()

        except Exception:

            return None