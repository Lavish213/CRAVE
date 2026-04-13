from __future__ import annotations

import logging
from typing import Dict, List, Optional
from urllib.parse import urlencode

import requests

from app.db.models.place import Place


logger = logging.getLogger(__name__)


GOOGLE_PHOTO_API = "https://maps.googleapis.com/maps/api/place/photo"
GOOGLE_PLACE_DETAILS = "https://maps.googleapis.com/maps/api/place/details/json"

MAX_GOOGLE_IMAGES = 20
DEFAULT_MAX_WIDTH = 1600
REQUEST_TIMEOUT = 5


class GoogleImageFetcher:
    """
    Fetch image candidates from Google Places / Google Maps.

    Uses the Google Place Details API to retrieve photo references
    and then converts those into image URLs.

    Returned structure matches the ImageCandidate contract.
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> None:

        self.api_key = api_key
        self.session = session or requests.Session()

    def fetch(
        self,
        *,
        place: Place,
    ) -> List[dict]:

        place_name = getattr(place, "name", None)
        place_id = getattr(place, "id", None)

        if not place_name:
            return []

        try:

            photos = self._fetch_photo_references(place=place)

            if not photos:
                return []

            candidates = []

            for photo in photos[:MAX_GOOGLE_IMAGES]:

                try:

                    url = self._build_photo_url(photo_reference=photo)

                    if not url:
                        continue

                    candidate: Dict[str, object] = {
                        "url": url,
                        "source": "google",
                        "width": photo.get("width"),
                        "height": photo.get("height"),
                        "context": "google_places",
                        "metadata": {
                            "photo_reference": photo.get("photo_reference"),
                            "html_attributions": photo.get("html_attributions"),
                        },
                    }

                    candidates.append(candidate)

                except Exception as exc:

                    logger.debug(
                        "google_image_candidate_failed place_id=%s error=%s",
                        place_id,
                        exc,
                    )

            logger.info(
                "google_images_fetched place_id=%s count=%s",
                place_id,
                len(candidates),
            )

            return candidates

        except Exception as exc:

            logger.debug(
                "google_image_fetch_failed place_id=%s error=%s",
                place_id,
                exc,
            )

            return []

    # ---------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------

    def _fetch_photo_references(
        self,
        *,
        place: Place,
    ) -> List[dict]:

        if not self.api_key:
            return []

        lat = getattr(place, "lat", None)
        lng = getattr(place, "lng", None)

        if lat is None or lng is None:
            return []

        params = {
            "key": self.api_key,
            "fields": "photos",
            "input": f"{lat},{lng}",
            "inputtype": "textquery",
        }

        try:

            url = GOOGLE_PLACE_DETAILS + "?" + urlencode(params)

            response = self.session.get(
                url,
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code != 200:
                return []

            payload = response.json()

            result = payload.get("result")

            if not result:
                return []

            photos = result.get("photos")

            if not photos:
                return []

            return photos

        except Exception:

            return []

    def _build_photo_url(
        self,
        *,
        photo_reference: Dict,
    ) -> Optional[str]:

        ref = photo_reference.get("photo_reference")

        if not ref:
            return None

        params = {
            "maxwidth": DEFAULT_MAX_WIDTH,
            "photoreference": ref,
            "key": self.api_key,
        }

        return GOOGLE_PHOTO_API + "?" + urlencode(params)