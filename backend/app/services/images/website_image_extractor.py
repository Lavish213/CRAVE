from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.db.models.place_image_fetch_log import PlaceImageFetchLog


logger = logging.getLogger(__name__)

UTC = timezone.utc

REQUEST_TIMEOUT = 6
MAX_WEBSITE_IMAGES = 30
MIN_IMAGE_LENGTH = 60
FETCH_CACHE_HOURS = 24


def _utcnow() -> datetime:
    return datetime.now(UTC)


class WebsiteImageExtractor:
    """
    Extract image candidates from a restaurant's official website.

    Improvements
    ------------
    - avoids repeated scraping via fetch cache
    - extracts OpenGraph / Twitter images
    - parses <img> tags
    - resolves relative urls
    - removes logos / icons / svg assets
    - prevents repeated domain scraping
    """

    def __init__(
        self,
        *,
        session: Optional[requests.Session] = None,
    ) -> None:

        self.session = session or requests.Session()

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    def extract(
        self,
        *,
        db: Optional[Session] = None,
        place: Place,
    ) -> List[dict]:

        place_id = getattr(place, "id", None)

        # Priority: official website > menu_source_url > grubhub_url
        # grubhub_url is a Grubhub SPA page — og:image may not be present in
        # static HTML, but we still attempt it as a best-effort fallback.
        website = (
            getattr(place, "website", None)
            or getattr(place, "menu_source_url", None)
            or getattr(place, "grubhub_url", None)
        )

        if not website:
            return []

        source_tag = "website"
        if not getattr(place, "website", None):
            source_tag = "grubhub" if getattr(place, "grubhub_url", None) else "provider"

        if db is not None and self._recently_fetched(
            db=db,
            place_id=place_id,
            source=source_tag,
        ):
            return []

        try:

            html = self._fetch_html(website)

            if not html:
                return []

            soup = BeautifulSoup(html, "html.parser")

            candidates: List[dict] = []

            candidates.extend(self._extract_meta_images(soup, website))
            candidates.extend(self._extract_img_tags(soup, website))

            candidates = self._filter_images(candidates)

            if db is not None:
                self._record_fetch(
                    db=db,
                    place_id=place_id,
                    source=source_tag,
                )

            return candidates[:MAX_WEBSITE_IMAGES]

        except Exception as exc:

            logger.debug(
                "website_image_extract_failed place_id=%s error=%s",
                place_id,
                exc,
            )

            return []

    # ---------------------------------------------------------
    # Fetch caching
    # ---------------------------------------------------------

    def _recently_fetched(
        self,
        *,
        db: Session,
        place_id: str,
        source: str,
    ) -> bool:

        cutoff = _utcnow() - timedelta(hours=FETCH_CACHE_HOURS)

        stmt = (
            select(PlaceImageFetchLog)
            .where(
                PlaceImageFetchLog.place_id == place_id,
                PlaceImageFetchLog.source == source,
                PlaceImageFetchLog.fetched_at > cutoff,
            )
        )

        return db.execute(stmt).scalar_one_or_none() is not None

    def _record_fetch(
        self,
        *,
        db: Session,
        place_id: str,
        source: str,
    ) -> None:

        try:

            log = PlaceImageFetchLog(
                place_id=place_id,
                source=source,
                fetched_at=_utcnow(),
            )

            db.add(log)

        except Exception:
            pass

    # ---------------------------------------------------------
    # Fetch
    # ---------------------------------------------------------

    def _fetch_html(
        self,
        website: str,
    ) -> Optional[str]:

        try:

            response = self.session.get(
                website,
                timeout=REQUEST_TIMEOUT,
                headers={
                    "User-Agent": "Mozilla/5.0 (FoodDiscoveryBot)"
                },
            )

            if response.status_code != 200:
                return None

            return response.text

        except Exception:
            return None

    # ---------------------------------------------------------
    # Extractors
    # ---------------------------------------------------------

    def _extract_meta_images(
        self,
        soup: BeautifulSoup,
        base_url: str,
    ) -> List[dict]:

        images: List[dict] = []

        metas = soup.find_all("meta")

        for meta in metas:

            prop = meta.get("property") or meta.get("name")

            if prop not in {"og:image", "twitter:image"}:
                continue

            url = meta.get("content")

            if not url:
                continue

            images.append(
                self._build_candidate(
                    urljoin(base_url, url),
                    context="meta_tag",
                )
            )

        return images

    def _extract_img_tags(
        self,
        soup: BeautifulSoup,
        base_url: str,
    ) -> List[dict]:

        images: List[dict] = []

        tags = soup.find_all("img")

        for tag in tags:

            src = tag.get("src")

            if not src:
                continue

            url = urljoin(base_url, src)

            images.append(
                self._build_candidate(
                    url,
                    context="img_tag",
                )
            )

        return images

    # ---------------------------------------------------------
    # Candidate builder
    # ---------------------------------------------------------

    def _build_candidate(
        self,
        url: str,
        context: str,
    ) -> dict:

        return {
            "url": url,
            "source": "website",
            "width": None,
            "height": None,
            "context": context,
            "metadata": {},
        }

    # ---------------------------------------------------------
    # Filtering
    # ---------------------------------------------------------

    def _filter_images(
        self,
        images: List[dict],
    ) -> List[dict]:

        filtered: List[dict] = []
        seen = set()

        for img in images:

            url = img.get("url")

            if not url:
                continue

            if url in seen:
                continue

            seen.add(url)

            if len(url) < MIN_IMAGE_LENGTH:
                continue

            parsed = urlparse(url)

            path = parsed.path.lower()

            if any(
                x in path
                for x in [
                    "logo",
                    "icon",
                    "sprite",
                    "favicon",
                    ".svg",
                ]
            ):
                continue

            filtered.append(img)

        return filtered