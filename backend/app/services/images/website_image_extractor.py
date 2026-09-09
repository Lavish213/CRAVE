from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.db.models.place_image_fetch_log import PlaceImageFetchLog
from app.services.network.browser_escalation import fetch_with_browser


logger = logging.getLogger(__name__)

UTC = timezone.utc

REQUEST_TIMEOUT = 6
MAX_WEBSITE_IMAGES = 30
FETCH_CACHE_HOURS = 24

_IMAGE_META_PROPERTIES = {
    "og:image",
    "og:image:url",
    "og:image:secure_url",
    "twitter:image",
    "twitter:image:src",
}
_STRUCTURED_IMAGE_KEYS = {"image", "photo", "photos", "primaryImageOfPage", "thumbnailUrl"}
_STRUCTURED_IMAGE_URL_KEYS = {"contentUrl", "url", "thumbnailUrl"}
_NON_IMAGE_SUFFIXES = {
    ".css", ".js", ".json", ".html", ".htm", ".pdf", ".xml", ".zip",
}
_CSS_URL_RE = re.compile(r"url\(\s*['\"]?([^)'\"]+)['\"]?\s*\)", re.IGNORECASE)


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
            candidates: List[dict] = (
                self._extract_from_html(html, website) if html else []
            )

            # A modern site (Squarespace/Wix/React, lazy-loaded galleries,
            # CSS background-images) commonly renders its photos client-side
            # -- a plain GET + static parse then finds nothing, which reads
            # as "no free images exist" when it's really "this site needs
            # JS to render." Escalate to the same headless-browser renderer
            # the menu pipeline already uses (browser_escalation.py) before
            # ever falling back to a paid Google lookup.
            if not candidates:
                rendered_html = self._fetch_html_via_browser(website)
                if rendered_html:
                    candidates = self._extract_from_html(rendered_html, website)
                    if candidates:
                        logger.info(
                            "website_image_browser_escalation_success place_id=%s",
                            place_id,
                        )

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

    def _fetch_html_via_browser(
        self,
        website: str,
    ) -> Optional[str]:

        try:
            return fetch_with_browser(website, referer=website)
        except Exception as exc:
            logger.debug(
                "website_image_browser_fetch_failed website=%s error=%s",
                website,
                exc,
            )
            return None

    def _extract_from_html(
        self,
        html: str,
        base_url: str,
    ) -> List[dict]:

        soup = BeautifulSoup(html, "html.parser")

        candidates: List[dict] = []
        candidates.extend(self._extract_meta_images(soup, base_url))
        candidates.extend(self._extract_link_images(soup, base_url))
        candidates.extend(self._extract_jsonld_images(soup, base_url))
        candidates.extend(self._extract_img_tags(soup, base_url))
        candidates.extend(self._extract_picture_sources(soup, base_url))
        candidates.extend(self._extract_inline_background_images(soup, base_url))

        return self._filter_images(candidates)

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

            if str(prop or "").lower() not in _IMAGE_META_PROPERTIES:
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

    def _extract_link_images(self, soup: BeautifulSoup, base_url: str) -> List[dict]:
        images: List[dict] = []
        for tag in soup.find_all("link"):
            rel = {str(value).lower() for value in (tag.get("rel") or [])}
            is_image_preload = "preload" in rel and str(tag.get("as") or "").lower() == "image"
            if "image_src" not in rel and not is_image_preload:
                continue
            url = tag.get("href") or tag.get("imagesrcset")
            if url:
                images.append(self._build_candidate(urljoin(base_url, self._best_srcset_url(url)), "link_tag"))
        return images

    def _extract_jsonld_images(self, soup: BeautifulSoup, base_url: str) -> List[dict]:
        images: List[dict] = []

        def add_value(value, *, context: str = "json_ld") -> None:
            if isinstance(value, str):
                images.append(self._build_candidate(urljoin(base_url, value), context))
                return
            if isinstance(value, list):
                for item in value:
                    add_value(item, context=context)
                return
            if not isinstance(value, dict):
                return
            for key in _STRUCTURED_IMAGE_URL_KEYS:
                url = value.get(key)
                if isinstance(url, str):
                    candidate = self._build_candidate(urljoin(base_url, url), context)
                    candidate["width"] = self._numeric_dimension(value.get("width"))
                    candidate["height"] = self._numeric_dimension(value.get("height"))
                    images.append(candidate)
                    break

        def walk(value) -> None:
            if isinstance(value, list):
                for item in value:
                    walk(item)
                return
            if not isinstance(value, dict):
                return
            for key, child in value.items():
                if key in _STRUCTURED_IMAGE_KEYS:
                    add_value(child)
                elif key != "logo":
                    walk(child)

        for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                walk(json.loads(tag.string or tag.get_text() or ""))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
        return images

    @staticmethod
    def _numeric_dimension(value):
        if isinstance(value, dict):
            value = value.get("value")
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _best_srcset_url(srcset: str) -> str:
        candidates = []
        for index, part in enumerate(srcset.split(",")):
            tokens = part.strip().split()
            if not tokens:
                continue
            score = float(index)
            if len(tokens) > 1:
                descriptor = tokens[-1].lower()
                try:
                    if descriptor.endswith("w"):
                        score = float(descriptor[:-1])
                    elif descriptor.endswith("x"):
                        score = float(descriptor[:-1]) * 10000
                except ValueError:
                    pass
            candidates.append((score, tokens[0]))
        return max(candidates, default=(0, ""), key=lambda item: item[0])[1]

    def _extract_img_tags(
        self,
        soup: BeautifulSoup,
        base_url: str,
    ) -> List[dict]:

        images: List[dict] = []

        tags = soup.find_all("img")

        for tag in tags:

            # Real src first; a static-only fetch commonly finds a lazy-load
            # gallery where the real image only lives in one of these
            # attributes until JS swaps it in (src is a 1x1 placeholder).
            src = (
                tag.get("data-src")
                or tag.get("data-lazy-src")
                or tag.get("data-original")
                or tag.get("src")
            )

            if not src:
                srcset = tag.get("srcset") or tag.get("data-srcset")
                if srcset:
                    # First candidate is good enough here -- _filter_images
                    # and the downstream scorer decide real quality, this
                    # step only needs *a* usable URL.
                    src = self._best_srcset_url(srcset)

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

    def _extract_picture_sources(self, soup: BeautifulSoup, base_url: str) -> List[dict]:
        images: List[dict] = []
        for tag in soup.select("picture source[srcset], picture source[data-srcset]"):
            src = self._best_srcset_url(tag.get("srcset") or tag.get("data-srcset") or "")
            if src:
                images.append(self._build_candidate(urljoin(base_url, src), "picture_source"))
        return images

    def _extract_inline_background_images(self, soup: BeautifulSoup, base_url: str) -> List[dict]:
        images: List[dict] = []
        for tag in soup.select("[style]"):
            style = str(tag.get("style") or "")
            if "background" not in style.lower():
                continue
            for url in _CSS_URL_RE.findall(style):
                images.append(self._build_candidate(urljoin(base_url, url), "inline_background"))
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

            parsed = urlparse(url)

            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                continue

            path = parsed.path.lower()

            if any(path.endswith(suffix) for suffix in _NON_IMAGE_SUFFIXES):
                continue

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
