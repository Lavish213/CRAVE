from __future__ import annotations

import logging
from typing import Dict, List, Optional

from app.db.models.place import Place

from app.services.images.google_image_fetcher import GoogleImageFetcher
from app.services.images.provider_image_extractor import ProviderImageExtractor
from app.services.images.website_image_extractor import WebsiteImageExtractor


logger = logging.getLogger(__name__)


MAX_SOURCE_IMAGES = 30


class ImageReader:
    """
    Collect raw image candidates from all sources.

    Sources
    -------
    google
    delivery providers
    official website

    Output
    ------
    normalized candidate dictionaries
    """

    def __init__(
        self,
        *,
        google_fetcher: Optional[GoogleImageFetcher] = None,
        provider_extractor: Optional[ProviderImageExtractor] = None,
        website_extractor: Optional[WebsiteImageExtractor] = None,
    ) -> None:
        self.google_fetcher = google_fetcher or GoogleImageFetcher()
        self.provider_extractor = provider_extractor or ProviderImageExtractor()
        self.website_extractor = website_extractor or WebsiteImageExtractor()

    def read(
        self,
        *,
        place: Place,
    ) -> List[dict]:

        place_id = getattr(place, "id", None)

        logger.debug(
            "image_reader_start place_id=%s place_name=%s",
            place_id,
            getattr(place, "name", None),
        )

        candidates: List[dict] = []

        candidates.extend(self._read_google(place))
        candidates.extend(self._read_provider(place))
        candidates.extend(self._read_website(place))

        if not candidates:
            logger.debug(
                "image_reader_no_candidates place_id=%s",
                place_id,
            )
            return []

        normalized = self._normalize_candidates(
            place=place,
            candidates=candidates,
        )

        logger.info(
            "image_reader_complete place_id=%s raw=%s normalized=%s",
            place_id,
            len(candidates),
            len(normalized),
        )

        return normalized

    # ---------------------------------------------------------
    # Source Readers
    # ---------------------------------------------------------

    def _read_google(
        self,
        place: Place,
    ) -> List[dict]:

        try:
            images = self.google_fetcher.fetch(place=place)

            if not images:
                return []

            return images[:MAX_SOURCE_IMAGES]

        except Exception as exc:
            logger.debug(
                "google_image_fetch_failed place_id=%s error=%s",
                getattr(place, "id", None),
                exc,
            )
            return []

    def _read_provider(
        self,
        place: Place,
    ) -> List[dict]:

        try:
            images = self.provider_extractor.extract(place=place)

            if not images:
                return []

            return images[:MAX_SOURCE_IMAGES]

        except Exception as exc:
            logger.debug(
                "provider_image_extract_failed place_id=%s error=%s",
                getattr(place, "id", None),
                exc,
            )
            return []

    def _read_website(
        self,
        place: Place,
    ) -> List[dict]:

        try:
            images = self.website_extractor.extract(place=place)

            if not images:
                return []

            return images[:MAX_SOURCE_IMAGES]

        except Exception as exc:
            logger.debug(
                "website_image_extract_failed place_id=%s error=%s",
                getattr(place, "id", None),
                exc,
            )
            return []

    # ---------------------------------------------------------
    # Candidate Normalization
    # ---------------------------------------------------------

    def _normalize_candidates(
        self,
        *,
        place: Place,
        candidates: List[dict],
    ) -> List[dict]:

        normalized: List[dict] = []

        place_id = getattr(place, "id", None)

        for candidate in candidates:

            try:

                url = candidate.get("url")

                if not url:
                    continue

                source = candidate.get("source") or "unknown"

                width = candidate.get("width")
                height = candidate.get("height")

                normalized_candidate: Dict[str, object] = {
                    "place_id": place_id,
                    "url": str(url).strip(),
                    "source": source,
                    "width": width,
                    "height": height,
                    "context": candidate.get("context"),
                    "metadata": candidate.get("metadata", {}),
                }

                normalized.append(normalized_candidate)

            except Exception as exc:

                logger.debug(
                    "image_candidate_normalization_failed error=%s",
                    exc,
                )

        return normalized