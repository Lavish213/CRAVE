from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

import requests

from app.db.models.place import Place


logger = logging.getLogger(__name__)

_GOOGLE_API_KEY_ENV = "GOOGLE_PLACES_API_KEY"

GOOGLE_SEARCH_TEXT = "https://places.googleapis.com/v1/places:searchText"

MAX_GOOGLE_IMAGES = 20
DEFAULT_MAX_WIDTH = 1600
REQUEST_TIMEOUT = 5

_API_CALL_COUNTER: dict = {"total": 0}


def reset_api_call_counter() -> None:
    _API_CALL_COUNTER["total"] = 0


def get_api_call_count() -> int:
    return _API_CALL_COUNTER["total"]


class GoogleImageFetcher:

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.api_key = api_key or os.environ.get(_GOOGLE_API_KEY_ENV, "").strip() or None
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
                    photo_name = self._extract_photo_name(photo)

                    if not photo_name:
                        continue

                    candidate: Dict[str, object] = {
                        "url": photo_name,
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

    def _fetch_photo_references(
        self,
        *,
        place: Place,
    ) -> List[dict]:
        if not self.api_key:
            return []

        place_name = getattr(place, "name", None)
        lat = getattr(place, "lat", None)
        lng = getattr(place, "lng", None)

        if not place_name:
            return []

        body: dict = {
            "textQuery": place_name,
            "maxResultCount": 1,
        }
        if lat is not None and lng is not None:
            body["locationBias"] = {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": 200.0,
                }
            }

        try:
            resp = self.session.post(
                GOOGLE_SEARCH_TEXT,
                headers={
                    "X-Goog-Api-Key": self.api_key,
                    "X-Goog-FieldMask": "places.id,places.photos",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=REQUEST_TIMEOUT,
            )
            _API_CALL_COUNTER["total"] += 1
            if _API_CALL_COUNTER["total"] % 10 == 0:
                logger.info(
                    "google_api_calls_made total=%s",
                    _API_CALL_COUNTER["total"],
                )
            if resp.status_code != 200:
                logger.debug(
                    "google_search_text_error place=%s status=%s",
                    place_name, resp.status_code,
                )
                return []

            data = resp.json()
            places = data.get("places", [])
            if not places:
                return []

            return places[0].get("photos", [])

        except Exception as exc:
            logger.debug(
                "google_search_text_failed place=%s error=%s",
                place_name, exc,
            )
            return []

    def _extract_photo_name(
        self,
        *,
        photo_reference: Dict,
    ) -> Optional[str]:
        return photo_reference.get("name") or None

    def _build_photo_url(
        self,
        *,
        photo_reference: Dict,
    ) -> Optional[str]:
        photo_name = photo_reference.get("name")
        if not photo_name:
            return None
        return (
            f"https://places.googleapis.com/v1/{photo_name}/media"
            f"?maxWidthPx={DEFAULT_MAX_WIDTH}&key={self.api_key}"
        )
