from __future__ import annotations

import re
import json
import logging
from typing import List, Optional, Set


from app.services.network.http_fetcher import fetch
from app.services.menu.contracts import ExtractedMenu, ExtractedMenuItem
from app.services.menu.extraction.provider_detector import detect_provider


logger = logging.getLogger(__name__)


MAX_PROVIDER_ITEMS = 1200


# ---------------------------------------------------------
# Item helpers
# ---------------------------------------------------------

def _normalize_price(price) -> Optional[str]:

    if price is None:
        return None

    try:
        return str(price)
    except Exception:
        return None


def _normalize_name(name) -> Optional[str]:

    if not name:
        return None

    name = str(name).strip()

    if not name:
        return None

    return name


def _dedupe_items(items: List[ExtractedMenuItem]) -> List[ExtractedMenuItem]:

    seen: Set[str] = set()
    unique: List[ExtractedMenuItem] = []

    for item in items:

        key = (
            f"{(item.name or '').strip().lower()}|"
            f"{(item.price or '').strip()}|"
            f"{(item.section or '').strip().lower()}"
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(item)

        if len(unique) >= MAX_PROVIDER_ITEMS:
            break

    return unique


# ---------------------------------------------------------
# Safe JSON fetch
# ---------------------------------------------------------

def _safe_json_fetch(url: str) -> Optional[dict]:

    try:

        response = fetch(url, method="GET")

        if response.status_code != 200:
            return None

        content_type = response.headers.get("content-type", "").lower()

        if "json" not in content_type:
            return None

        return response.json()

    except Exception as exc:

        logger.debug(
            "provider_fetch_failed url=%s error=%s",
            url,
            exc,
        )

        return None


# ---------------------------------------------------------
# Provider extractors
# ---------------------------------------------------------

_TOAST_MENU_RE = re.compile(r'"menuApi"\s*:\s*"([^"]+)"')


def _fetch_toast_menu(html: str) -> List[ExtractedMenuItem]:

    items: List[ExtractedMenuItem] = []

    match = _TOAST_MENU_RE.search(html)

    if not match:
        return items

    api_url = match.group(1)

    data = _safe_json_fetch(api_url)

    if not data:
        return items

    groups = data.get("groups") or []

    for group in groups:

        section = group.get("name")

        for item in group.get("items", []):

            name = _normalize_name(item.get("name"))
            price = _normalize_price(item.get("price"))

            if not name:
                continue

            items.append(
                ExtractedMenuItem(
                    name=name,
                    price=price,
                    section=section,
                    currency="USD",
                )
            )

    return items


_SQUARE_MENU_RE = re.compile(r'"menu"\s*:\s*(\{.*?\})', re.S)


def _fetch_square_menu(html: str) -> List[ExtractedMenuItem]:

    items: List[ExtractedMenuItem] = []

    match = _SQUARE_MENU_RE.search(html)

    if not match:
        return items

    try:
        data = json.loads(match.group(1))
    except Exception:
        return items

    for category in data.get("categories", []):

        section = category.get("name")

        for item in category.get("items", []):

            name = _normalize_name(item.get("name"))
            price = _normalize_price(item.get("price"))

            if not name:
                continue

            items.append(
                ExtractedMenuItem(
                    name=name,
                    price=price,
                    section=section,
                    currency="USD",
                )
            )

    return items


_OLO_MENU_RE = re.compile(r'"menuUrl"\s*:\s*"([^"]+)"')


def _fetch_olo_menu(html: str) -> List[ExtractedMenuItem]:

    items: List[ExtractedMenuItem] = []

    match = _OLO_MENU_RE.search(html)

    if not match:
        return items

    api_url = match.group(1)

    data = _safe_json_fetch(api_url)

    if not data:
        return items

    for category in data.get("categories", []):

        section = category.get("name")

        for product in category.get("products", []):

            name = _normalize_name(product.get("name"))
            price = _normalize_price(product.get("price"))

            if not name:
                continue

            items.append(
                ExtractedMenuItem(
                    name=name,
                    price=price,
                    section=section,
                    currency="USD",
                )
            )

    return items


_CHOWNOW_MENU_RE = re.compile(r'"menu_url"\s*:\s*"([^"]+)"')


def _fetch_chownow_menu(html: str) -> List[ExtractedMenuItem]:

    items: List[ExtractedMenuItem] = []

    match = _CHOWNOW_MENU_RE.search(html)

    if not match:
        return items

    api_url = match.group(1)

    data = _safe_json_fetch(api_url)

    if not data:
        return items

    for category in data.get("categories", []):

        section = category.get("name")

        for item in category.get("items", []):

            name = _normalize_name(item.get("name"))
            price = _normalize_price(item.get("price"))

            if not name:
                continue

            items.append(
                ExtractedMenuItem(
                    name=name,
                    price=price,
                    section=section,
                    currency="USD",
                )
            )

    return items


# ---------------------------------------------------------
# Public API
# ---------------------------------------------------------

def fetch_provider_menu(
    *,
    url: str,
    html: str,
) -> Optional[ExtractedMenu]:

    provider = detect_provider(html, url)

    if not provider:
        return None

    provider = provider.lower()

    items: List[ExtractedMenuItem] = []

    try:

        if provider == "toast":
            items = _fetch_toast_menu(html)

        elif provider == "square":
            items = _fetch_square_menu(html)

        elif provider == "olo":
            items = _fetch_olo_menu(html)

        elif provider == "chownow":
            items = _fetch_chownow_menu(html)

    except Exception as exc:

        logger.debug(
            "provider_parse_failed provider=%s url=%s error=%s",
            provider,
            url,
            exc,
        )

        return None

    if not items:

        logger.debug(
            "provider_menu_not_found provider=%s url=%s",
            provider,
            url,
        )

        return None

    items = _dedupe_items(items)

    logger.info(
        "provider_menu_success provider=%s url=%s items=%s",
        provider,
        url,
        len(items),
    )

    return ExtractedMenu(
        items=items,
        source_url=url,
    )