from __future__ import annotations

import logging
from typing import Dict, List, Optional

from app.db.models.place import Place


logger = logging.getLogger(__name__)


MAX_PROVIDER_IMAGES = 25


class ProviderImageExtractor:
    """
    Extract images from delivery/provider sources.

    Intended sources:
    - UberEats
    - DoorDash
    - Grubhub
    - Yelp style provider feeds

    Provider data may come from discovery ingestion payloads or
    raw provider API payloads stored in candidate metadata.

    The extractor normalizes those into image candidates.
    """

    def extract(
        self,
        *,
        place: Place,
    ) -> List[dict]:

        place_id = getattr(place, "id", None)

        try:

            payloads = self._provider_payloads(place)

            if not payloads:
                return []

            images: List[dict] = []

            for payload in payloads:

                extracted = self._extract_images_from_payload(payload)

                if extracted:
                    images.extend(extracted)

            images = images[:MAX_PROVIDER_IMAGES]

            logger.info(
                "provider_images_extracted place_id=%s count=%s",
                place_id,
                len(images),
            )

            return images

        except Exception as exc:

            logger.debug(
                "provider_image_extract_failed place_id=%s error=%s",
                place_id,
                exc,
            )

            return []

    # ---------------------------------------------------------
    # Payload discovery
    # ---------------------------------------------------------

    def _provider_payloads(
        self,
        place: Place,
    ) -> List[Dict]:

        payloads: List[Dict] = []

        claims = getattr(place, "claims", None)

        if not claims:
            return payloads

        for claim in claims:

            try:

                value = getattr(claim, "value_json", None)

                if not isinstance(value, dict):
                    continue

                source_type = value.get("source_type")

                if source_type not in {
                    "provider_api",
                    "provider_scrape",
                    "delivery_provider",
                }:
                    continue

                payloads.append(value)

            except Exception:
                continue

        return payloads

    # ---------------------------------------------------------
    # Image extraction
    # ---------------------------------------------------------

    def _extract_images_from_payload(
        self,
        payload: Dict,
    ) -> List[dict]:

        images: List[dict] = []

        image_candidates = payload.get("images")

        if isinstance(image_candidates, list):

            for img in image_candidates:

                candidate = self._normalize_provider_image(img)

                if candidate:
                    images.append(candidate)

        hero = payload.get("hero_image")

        if hero:

            candidate = self._normalize_provider_image(hero)

            if candidate:
                images.append(candidate)

        logo = payload.get("logo")

        if logo:

            candidate = self._normalize_provider_image(logo)

            if candidate:
                images.append(candidate)

        return images

    # ---------------------------------------------------------
    # Normalization
    # ---------------------------------------------------------

    def _normalize_provider_image(
        self,
        image_payload,
    ) -> Optional[dict]:

        try:

            if isinstance(image_payload, str):

                url = image_payload
                width = None
                height = None

            elif isinstance(image_payload, dict):

                url = image_payload.get("url")
                width = image_payload.get("width")
                height = image_payload.get("height")

            else:
                return None

            if not url:
                return None

            return {
                "url": str(url).strip(),
                "source": "provider",
                "width": width,
                "height": height,
                "context": "provider_feed",
                "metadata": {},
            }

        except Exception:

            return None