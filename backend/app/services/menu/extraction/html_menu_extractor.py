from __future__ import annotations

import json
import logging
import re
from typing import Iterable, List, Optional, Set

from bs4 import BeautifulSoup, Tag

from app.services.menu.contracts import ExtractedMenu, ExtractedMenuItem
from app.services.menu.extraction.heuristics import (
    clean_text,
    detect_menu_containers,
    extract_price,
    extract_section_headers,
    is_junk_line,
)


logger = logging.getLogger(__name__)


MAX_MENU_ITEMS = 1000
MAX_HTML_LENGTH = 3_000_000
MAX_NODE_SCAN = 12000

_TRAILING_SEP_RE = re.compile(r"[\-|–|:]+$")
_PRICE_INLINE_RE = re.compile(r"\$\s?\d+(?:\.\d{1,2})?")
_PRICE_FIRST_RE = re.compile(
    r"^(?P<price>\$?\s?\d+(?:\.\d{1,2})?)\s+(?P<name>.+)$"
)
_DESCRIPTION_RE = re.compile(r"([A-Za-z].{10,})")


# ---------------------------------------------------------
# CLEAN
# ---------------------------------------------------------

def _clean_item_name(name: str) -> str:
    value = (name or "").strip()
    value = _TRAILING_SEP_RE.sub("", value)
    return value.strip()


def _build_item_key(name: str, price: str | None, section: str | None) -> str:
    return f"{(name or '').strip().lower()}|{(price or '').strip()}|{(section or '').strip().lower()}"


def _normalize_price(price: str | None) -> Optional[str]:
    if not price:
        return None

    value = str(price).strip().replace("$", "").strip()
    return value or None


# ---------------------------------------------------------
# JSON-LD (fallback inside html extractor)
# ---------------------------------------------------------

def _flatten_json_ld(data) -> Iterable[dict]:
    if isinstance(data, list):
        for item in data:
            yield from _flatten_json_ld(item)
        return

    if isinstance(data, dict):
        yield data

        graph = data.get("@graph")
        if graph is not None:
            yield from _flatten_json_ld(graph)


def _extract_offer_price(obj: dict) -> str | None:
    offers = obj.get("offers")

    if isinstance(offers, dict):
        return str(offers.get("price")) if offers.get("price") else None

    if isinstance(offers, list):
        for offer in offers:
            if isinstance(offer, dict) and offer.get("price"):
                return str(offer.get("price"))

    return None


def _extract_description_from_obj(obj: dict) -> Optional[str]:
    value = obj.get("description")
    if not value:
        return None
    return clean_text(str(value)) or None


# ---------------------------------------------------------
# ITEM BUILDER
# ---------------------------------------------------------

def _make_item(
    *,
    name: str,
    price: Optional[str],
    section: Optional[str],
    source_url: Optional[str],
    description: Optional[str] = None,
) -> Optional[ExtractedMenuItem]:

    clean_name = _clean_item_name(clean_text(name))

    if len(clean_name) < 2:
        return None

    return ExtractedMenuItem(
        name=clean_name,
        price=_normalize_price(price),
        section=clean_text(section) or None,
        currency="USD",
        description=clean_text(description) or None,
        source_url=source_url,
        source_type="html",
    )


# ---------------------------------------------------------
# JSON-LD
# ---------------------------------------------------------

def _extract_json_ld_items(
    soup: BeautifulSoup,
    seen: Set[str],
    source_url: Optional[str],
) -> List[ExtractedMenuItem]:

    items: List[ExtractedMenuItem] = []

    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text() or ""

        if not raw.strip():
            continue

        try:
            data = json.loads(raw)
        except Exception:
            continue

        for obj in _flatten_json_ld(data):

            if not isinstance(obj, dict):
                continue

            obj_type = obj.get("@type")
            if isinstance(obj_type, list):
                obj_type = obj_type[0] if obj_type else None

            if obj_type not in {"MenuItem", "Product"}:
                continue

            name = obj.get("name")
            if not name:
                continue

            item = _make_item(
                name=str(name),
                price=_extract_offer_price(obj),
                section=None,
                source_url=source_url,
                description=_extract_description_from_obj(obj),
            )

            if not item:
                continue

            key = _build_item_key(item.name, item.price, item.section)

            if key in seen:
                continue

            seen.add(key)
            items.append(item)

            if len(items) >= MAX_MENU_ITEMS:
                return items

    return items


# ---------------------------------------------------------
# TABLE
# ---------------------------------------------------------

def _extract_table_items(
    soup: BeautifulSoup,
    seen: Set[str],
    source_url: Optional[str],
) -> List[ExtractedMenuItem]:

    items: List[ExtractedMenuItem] = []

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])

            if len(cells) < 2:
                continue

            name = clean_text(cells[0].get_text(" ", strip=True))
            price = extract_price(cells[-1].get_text(" ", strip=True))

            if not name or not price:
                continue

            item = _make_item(
                name=name,
                price=price,
                section=None,
                source_url=source_url,
            )

            if not item:
                continue

            key = _build_item_key(item.name, item.price, item.section)

            if key in seen:
                continue

            seen.add(key)
            items.append(item)

            if len(items) >= MAX_MENU_ITEMS:
                return items

    return items


# ---------------------------------------------------------
# 🔥 NEW: LIST EXTRACTION (BIG WIN)
# ---------------------------------------------------------

def _extract_list_items(
    soup: BeautifulSoup,
    seen: Set[str],
    source_url: Optional[str],
) -> List[ExtractedMenuItem]:

    items: List[ExtractedMenuItem] = []

    for li in soup.find_all("li"):
        text = clean_text(li.get_text(" ", strip=True))

        if not text or is_junk_line(text):
            continue

        price = extract_price(text)
        if not price:
            continue

        name = text.split(price)[0].strip()
        if len(name) < 2:
            continue

        item = _make_item(
            name=name,
            price=price,
            section=None,
            source_url=source_url,
        )

        if not item:
            continue

        key = _build_item_key(item.name, item.price, item.section)

        if key in seen:
            continue

        seen.add(key)
        items.append(item)

        if len(items) >= MAX_MENU_ITEMS:
            return items

    return items


# ---------------------------------------------------------
# HEURISTIC CORE
# ---------------------------------------------------------

def _extract_heuristic_items(
    soup: BeautifulSoup,
    seen: Set[str],
    source_url: Optional[str],
) -> List[ExtractedMenuItem]:

    items: List[ExtractedMenuItem] = []

    containers = detect_menu_containers(soup) or [soup]

    scanned_nodes: Set[int] = set()
    node_counter = 0

    for container in containers:
        current_section: Optional[str] = None

        for node in container.descendants:

            if len(items) >= MAX_MENU_ITEMS:
                return items

            node_counter += 1
            if node_counter > MAX_NODE_SCAN:
                return items

            if not isinstance(node, Tag):
                continue

            node_id = id(node)
            if node_id in scanned_nodes:
                continue
            scanned_nodes.add(node_id)

            section = extract_section_headers(node)
            if section:
                current_section = section
                continue

            text = clean_text(node.get_text(" ", strip=True))

            if not text or is_junk_line(text):
                continue

            price = extract_price(text)

            if not price:
                inline = _PRICE_INLINE_RE.search(text)
                if inline:
                    price = inline.group(0)

            if not price:
                continue

            name = text.split(price)[0].strip()

            if not name:
                match = _PRICE_FIRST_RE.match(text)
                if match:
                    name = match.group("name").strip()
                    price = match.group("price")

            name = _clean_item_name(name)

            if len(name) < 2:
                continue

            desc = None
            desc_match = _DESCRIPTION_RE.search(text)

            if desc_match:
                candidate = clean_text(desc_match.group(0))
                if candidate and candidate != name:
                    desc = candidate

            item = _make_item(
                name=name,
                price=price,
                section=current_section,
                source_url=source_url,
                description=desc,
            )

            if not item:
                continue

            key = _build_item_key(item.name, item.price, item.section)

            if key in seen:
                continue

            seen.add(key)
            items.append(item)

    return items


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def extract_menu_from_html(
    html: str,
    source_url: str | None = None,
) -> ExtractedMenu:

    if not html:
        return ExtractedMenu(items=[], source_url=source_url, source_type="html")

    document = html[:MAX_HTML_LENGTH]
    soup = BeautifulSoup(document, "html.parser")

    seen: Set[str] = set()
    items: List[ExtractedMenuItem] = []

    try:
        items.extend(_extract_json_ld_items(soup, seen, source_url))
    except Exception as exc:
        logger.debug("html_jsonld_extraction_failed url=%s error=%s", source_url, exc)

    try:
        if len(items) < MAX_MENU_ITEMS:
            items.extend(_extract_table_items(soup, seen, source_url))
    except Exception as exc:
        logger.debug("html_table_extraction_failed url=%s error=%s", source_url, exc)

    try:
        if len(items) < MAX_MENU_ITEMS:
            items.extend(_extract_list_items(soup, seen, source_url))
    except Exception as exc:
        logger.debug("html_list_extraction_failed url=%s error=%s", source_url, exc)

    try:
        if len(items) < MAX_MENU_ITEMS:
            items.extend(_extract_heuristic_items(soup, seen, source_url))
    except Exception as exc:
        logger.debug("html_menu_extraction_failed url=%s error=%s", source_url, exc)

    trimmed = items[:MAX_MENU_ITEMS]

    logger.debug(
        "html_menu_extracted count=%s url=%s",
        len(trimmed),
        source_url,
    )

    return ExtractedMenu(
        items=trimmed,
        source_url=source_url,
        source_type="html",
    )


def extract_html_menu(
    html: str,
    source_url: str | None = None,
) -> List[ExtractedMenuItem]:

    result = extract_menu_from_html(html=html, source_url=source_url)
    return result.items