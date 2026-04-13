from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from app.services.ingest.toast_ingest import (
    ToastIngestResult,
    ToastRestaurantInput,
    ingest_toast_json_strings,
)
from app.services.network.http_fetcher import fetch


logger = logging.getLogger(__name__)

UUID_RE = re.compile(
    r"\b[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\b",
    re.IGNORECASE,
)

RESTAURANT_GUID_PATTERNS = (
    re.compile(r'"restaurantGuid"\s*:\s*"([a-f0-9\-]{36})"', re.IGNORECASE),
    re.compile(r'"guid"\s*:\s*"([a-f0-9\-]{36})"', re.IGNORECASE),
    re.compile(r"restaurantGuid\s*[:=]\s*['\"]([a-f0-9\-]{36})['\"]", re.IGNORECASE),
)

SCRIPT_SRC_RE = re.compile(
    r"""<script[^>]+src=["']([^"']+)["']""",
    re.IGNORECASE,
)

JSON_SCRIPT_RE = re.compile(
    r"""<script[^>]*type=["']application/(?:ld\+json|json)["'][^>]*>(.*?)</script>""",
    re.IGNORECASE | re.DOTALL,
)

INLINE_SCRIPT_RE = re.compile(
    r"""<script(?![^>]+src=)[^>]*>(.*?)</script>""",
    re.IGNORECASE | re.DOTALL,
)

SHORT_URL_RE = re.compile(
    r"""["']shortUrl["']\s*:\s*["']([^"']+)["']""",
    re.IGNORECASE,
)

NAME_RE = re.compile(
    r"""["']name["']\s*:\s*["']([^"']+)["']""",
    re.IGNORECASE,
)

CITY_RE = re.compile(
    r"""["']city["']\s*:\s*["']([^"']+)["']""",
    re.IGNORECASE,
)

STATE_RE = re.compile(
    r"""["']state["']\s*:\s*["']([^"']+)["']""",
    re.IGNORECASE,
)

ZIP_RE = re.compile(
    r"""["']zip["']\s*:\s*["']([^"']+)["']""",
    re.IGNORECASE,
)

ADDRESS1_RE = re.compile(
    r"""["']address1["']\s*:\s*["']([^"']+)["']""",
    re.IGNORECASE,
)

PHONE_RE = re.compile(
    r"""["']phone["']\s*:\s*["']([^"']+)["']""",
    re.IGNORECASE,
)

LAT_RE = re.compile(
    r"""["']latitude["']\s*:\s*(-?\d+(?:\.\d+)?)""",
    re.IGNORECASE,
)

LNG_RE = re.compile(
    r"""["']longitude["']\s*:\s*(-?\d+(?:\.\d+)?)""",
    re.IGNORECASE,
)


@dataclass(slots=True)
class ToastPageSignals:
    source_url: str
    page_title: Optional[str]
    restaurant_guid: Optional[str]
    short_url: Optional[str]
    restaurant_name: Optional[str]
    address1: Optional[str]
    city: Optional[str]
    state: Optional[str]
    zip_code: Optional[str]
    phone: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    script_urls: List[str]
    json_blobs: List[str]


@dataclass(slots=True)
class ToastPageScrapeResult:
    html: str
    signals: ToastPageSignals


def _safe_float(value: Optional[str]) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _title_from_html(html: str) -> Optional[str]:
    match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def _normalize_script_url(base_url: str, src: str) -> str:
    if src.startswith("http://") or src.startswith("https://"):
        return src
    if src.startswith("//"):
        return "https:" + src
    if src.startswith("/"):
        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}{src}"
    return src


def _extract_script_urls(html: str, base_url: str) -> List[str]:
    urls: List[str] = []
    seen = set()

    for raw in SCRIPT_SRC_RE.findall(html):
        url = _normalize_script_url(base_url, raw.strip())
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)

    return urls


def _extract_json_blobs(html: str) -> List[str]:
    blobs: List[str] = []

    for blob in JSON_SCRIPT_RE.findall(html):
        value = blob.strip()
        if value:
            blobs.append(value)

    return blobs


def _first_match(pattern: re.Pattern[str], text: str) -> Optional[str]:
    match = pattern.search(text)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def _extract_restaurant_guid(html: str) -> Optional[str]:
    for pattern in RESTAURANT_GUID_PATTERNS:
        value = _first_match(pattern, html)
        if value:
            return value

    all_uuids = UUID_RE.findall(html)
    return all_uuids[0] if all_uuids else None


def _extract_signals_from_html(url: str, html: str) -> ToastPageSignals:
    script_urls = _extract_script_urls(html, url)
    json_blobs = _extract_json_blobs(html)

    inline_scripts = INLINE_SCRIPT_RE.findall(html)
    joined_inline = "\n".join(s.strip() for s in inline_scripts if s.strip())

    restaurant_guid = _extract_restaurant_guid(html)
    short_url = _first_match(SHORT_URL_RE, html)
    restaurant_name = _first_match(NAME_RE, joined_inline) or _title_from_html(html)
    address1 = _first_match(ADDRESS1_RE, joined_inline)
    city = _first_match(CITY_RE, joined_inline)
    state = _first_match(STATE_RE, joined_inline)
    zip_code = _first_match(ZIP_RE, joined_inline)
    phone = _first_match(PHONE_RE, joined_inline)
    latitude = _safe_float(_first_match(LAT_RE, joined_inline))
    longitude = _safe_float(_first_match(LNG_RE, joined_inline))

    return ToastPageSignals(
        source_url=url,
        page_title=_title_from_html(html),
        restaurant_guid=restaurant_guid,
        short_url=short_url,
        restaurant_name=restaurant_name,
        address1=address1,
        city=city,
        state=state,
        zip_code=zip_code,
        phone=phone,
        latitude=latitude,
        longitude=longitude,
        script_urls=script_urls,
        json_blobs=json_blobs,
    )


def scrape_toast_page(url: str) -> ToastPageScrapeResult:
    response = fetch(
        url,
        mode="document",
        referer=url,
    )

    html = response.text if response.status_code == 200 else ""
    if not html:
        raise ValueError(f"toast_page_fetch_empty status={response.status_code} url={url}")

    signals = _extract_signals_from_html(url, html)

    logger.info(
        "toast_page_scraped url=%s guid=%s short_url=%s scripts=%s json_blobs=%s",
        url,
        signals.restaurant_guid,
        signals.short_url,
        len(signals.script_urls),
        len(signals.json_blobs),
    )

    return ToastPageScrapeResult(
        html=html,
        signals=signals,
    )


def _build_fallback_restaurant_payload(signals: ToastPageSignals) -> Optional[str]:
    if not signals.restaurant_guid:
        return None

    payload = [
        {
            "data": {
                "__typename": "Query",
                "restaurantV2": {
                    "__typename": "Restaurant",
                    "guid": signals.restaurant_guid,
                    "name": signals.restaurant_name,
                    "shortUrl": signals.short_url,
                    "location": {
                        "address1": signals.address1,
                        "city": signals.city,
                        "state": signals.state,
                        "zip": signals.zip_code,
                        "latitude": signals.latitude,
                        "longitude": signals.longitude,
                        "phone": signals.phone,
                    },
                },
            }
        }
    ]

    return json.dumps(payload)


def ingest_toast_page_with_payloads(
    *,
    db,
    url: str,
    city_id: str,
    payload_strings: List[str],
    confidence: float = 0.95,
) -> ToastIngestResult:
    scrape = scrape_toast_page(url)
    signals = scrape.signals

    merged_payloads: List[str] = []

    fallback_restaurant_payload = _build_fallback_restaurant_payload(signals)
    if fallback_restaurant_payload:
        merged_payloads.append(fallback_restaurant_payload)

    merged_payloads.extend(payload_strings)

    if not merged_payloads:
        raise ValueError("toast_page_ingest_no_payloads")

    return ingest_toast_json_strings(
        db=db,
        restaurant_input=ToastRestaurantInput(
            city_id=city_id,
            source_url=url,
            confidence=confidence,
        ),
        payload_strings=merged_payloads,
    )


def debug_toast_page(url: str) -> Dict[str, Any]:
    scrape = scrape_toast_page(url)
    signals = scrape.signals

    return {
        "source_url": signals.source_url,
        "page_title": signals.page_title,
        "restaurant_guid": signals.restaurant_guid,
        "short_url": signals.short_url,
        "restaurant_name": signals.restaurant_name,
        "address1": signals.address1,
        "city": signals.city,
        "state": signals.state,
        "zip_code": signals.zip_code,
        "phone": signals.phone,
        "latitude": signals.latitude,
        "longitude": signals.longitude,
        "script_urls": signals.script_urls,
        "json_blob_count": len(signals.json_blobs),
    }