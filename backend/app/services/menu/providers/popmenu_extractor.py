from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.services.network.http_fetcher import fetch
from app.services.menu.contracts import ExtractedMenuItem


logger = logging.getLogger(__name__)


MAX_ITEMS = 1200
MAX_RECURSION_DEPTH = 20


# ---------------------------------------------------------
# Popmenu patterns
# ---------------------------------------------------------

POPMENU_DOMAIN_PATTERN = re.compile(
    r"popmenu\.com",
    re.IGNORECASE,
)

POPMENU_MENU_PATTERN = re.compile(
    r'"menu"\s*:\s*(\{[\s\S]*?\})',
    re.DOTALL | re.IGNORECASE,
)

POPMENU_MENUS_PATTERN = re.compile(
    r'"menus"\s*:\s*(\[[\s\S]*?\])',
    re.DOTALL | re.IGNORECASE,
)

POPMENU_STATE_PATTERN = re.compile(
    r'window\.__INITIAL_STATE__\s*=\s*(\{[\s\S]*?\});',
    re.DOTALL,
)

POPMENU_API_PATTERN = re.compile(
    r'https://cdn\.popmenu\.com/.+?/menu\.json',
    re.IGNORECASE,
)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _safe_json_load(raw: str) -> Optional[Any]:

    if not raw:
        return None

    try:
        return json.loads(raw)
    except Exception:
        return None


def _safe_price(value: Any) -> Optional[str]:

    if value is None:
        return None

    try:

        if isinstance(value, (int, float)):

            if value > 100:
                return str(round(value / 100, 2))

            return str(value)

        if isinstance(value, str):

            value = value.replace("$", "").strip()

            return value

    except Exception:
        pass

    return None


def _normalize_name(value: Any) -> Optional[str]:

    if value is None:
        return None

    name = str(value).strip()

    if not name:
        return None

    return name


def _dedupe(items: List[ExtractedMenuItem]) -> List[ExtractedMenuItem]:

    seen = set()
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

        if len(unique) >= MAX_ITEMS:
            break

    return unique


# ---------------------------------------------------------
# API discovery
# ---------------------------------------------------------

def _discover_api(html: Optional[str]) -> Optional[str]:

    if not html:
        return None

    match = POPMENU_API_PATTERN.search(html)

    if match:
        return match.group(0)

    return None


def _fetch_api_menu(url: str) -> Optional[Any]:

    try:

        response = fetch(url)

        if response.status_code != 200:
            return None

        return response.json()

    except Exception:

        return None


# ---------------------------------------------------------
# JSON payload discovery
# ---------------------------------------------------------

def _find_menu_payload(html: Optional[str]) -> Optional[Any]:

    if not html:
        return None

    match = POPMENU_MENUS_PATTERN.search(html)

    if match:

        data = _safe_json_load(match.group(1))

        if data:
            return data

    match = POPMENU_MENU_PATTERN.search(html)

    if match:

        data = _safe_json_load(match.group(1))

        if data:
            return data

    match = POPMENU_STATE_PATTERN.search(html)

    if match:

        data = _safe_json_load(match.group(1))

        if data:
            return data

    return None


# ---------------------------------------------------------
# Recursive scanner
# ---------------------------------------------------------

def _scan(
    data: Any,
    *,
    items: List[ExtractedMenuItem],
    current_section: Optional[str] = None,
    depth: int = 0,
) -> None:

    if depth > MAX_RECURSION_DEPTH:
        return

    if len(items) >= MAX_ITEMS:
        return

    if isinstance(data, list):

        for value in data:
            _scan(value, items=items, current_section=current_section, depth=depth + 1)

        return

    if not isinstance(data, dict):
        return

    section = current_section

    if "name" in data and isinstance(data.get("items"), list):
        section = str(data["name"])

    if "name" in data and "price" in data:

        name = _normalize_name(data.get("name"))

        if name:

            price = _safe_price(data.get("price"))
            description = data.get("description")

            image = (
                data.get("image")
                or data.get("imageUrl")
                or data.get("image_url")
            )

            items.append(
                ExtractedMenuItem(
                    name=name,
                    price=price,
                    section=section,
                    currency="USD",
                    description=description,
                    image_url=image,
                    provider="popmenu",
                    source_type="provider",
                )
            )

    for value in data.values():

        if isinstance(value, (list, dict)):

            _scan(
                value,
                items=items,
                current_section=section,
                depth=depth + 1,
            )


# ---------------------------------------------------------
# Public extractor
# ---------------------------------------------------------

def extract_popmenu_menu(
    html: Optional[str] = None,
    url: Optional[str] = None,
) -> List[ExtractedMenuItem]:

    try:

        payload = None

        # try API first
        api_url = _discover_api(html)

        if api_url:

            payload = _fetch_api_menu(api_url)

        # fallback to embedded JSON
        if not payload:

            payload = _find_menu_payload(html)

        if not payload:

            logger.debug(
                "popmenu_payload_not_found url=%s",
                url,
            )

            return []

        items: List[ExtractedMenuItem] = []

        _scan(payload, items=items)

        items = _dedupe(items)

        if items:

            logger.info(
                "popmenu_menu_extracted url=%s items=%s",
                url,
                len(items),
            )

        return items

    except Exception as exc:

        logger.debug(
            "popmenu_menu_parse_failed url=%s error=%s",
            url,
            exc,
        )

        return []