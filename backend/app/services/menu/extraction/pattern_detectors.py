from __future__ import annotations

import json
import re
from typing import List, Set

from bs4 import BeautifulSoup

from app.services.menu.contracts import ExtractedMenuItem
from app.services.menu.extraction.heuristics import (
    clean_text,
    extract_price,
    extract_name_from_price_line,
    is_junk_line,
)

MAX_MENU_ITEMS = 1200

PRICE_REGEX = re.compile(r"\$\s?\d+(?:\.\d{1,2})?")

CARD_CLASSES = [
    "menu-item",
    "food-item",
    "dish",
    "menu-card",
    "product",
]


def _dedupe(items: List[ExtractedMenuItem]) -> List[ExtractedMenuItem]:

    seen: Set[str] = set()
    result: List[ExtractedMenuItem] = []

    for item in items:

        key = (
            f"{(item.name or '').strip().lower()}|"
            f"{(item.price or '').strip()}"
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(item)

        if len(result) >= MAX_MENU_ITEMS:
            break

    return result


def detect_menu_patterns(soup: BeautifulSoup) -> List[ExtractedMenuItem]:
    """
    Main pattern detection entrypoint.
    Runs detectors in order of reliability.
    """

    detectors = [
        detect_json_ld_menu,
        detect_table_menu,
        detect_menu_cards,
        detect_list_menu,
        detect_price_anchor_items,
        detect_fallback_items,
    ]

    for detector in detectors:

        items = detector(soup)

        if items:
            return items

    return []


def detect_json_ld_menu(soup: BeautifulSoup) -> List[ExtractedMenuItem]:

    items: List[ExtractedMenuItem] = []

    scripts = soup.find_all("script", type="application/ld+json")

    for script in scripts:

        raw = script.string

        if not raw:
            continue

        try:
            data = json.loads(raw)
        except Exception:
            continue

        if isinstance(data, dict):
            data = [data]

        if not isinstance(data, list):
            continue

        for obj in data:

            if not isinstance(obj, dict):
                continue

            if obj.get("@type") != "MenuItem":
                continue

            name = clean_text(obj.get("name"))

            if not name:
                continue

            price = None
            offers = obj.get("offers")

            if isinstance(offers, dict):
                price = offers.get("price")

            items.append(
                ExtractedMenuItem(
                    name=name,
                    price=str(price) if price else None,
                )
            )

    return _dedupe(items)


def detect_table_menu(soup: BeautifulSoup) -> List[ExtractedMenuItem]:

    items: List[ExtractedMenuItem] = []

    rows = soup.find_all("tr")

    for row in rows:

        cells = row.find_all(["td", "th"])

        if len(cells) < 2:
            continue

        name = clean_text(cells[0].get_text())
        price = extract_price(cells[-1].get_text())

        if not name:
            continue

        if is_junk_line(name):
            continue

        items.append(
            ExtractedMenuItem(
                name=name,
                price=price,
            )
        )

    return _dedupe(items)


def detect_list_menu(soup: BeautifulSoup) -> List[ExtractedMenuItem]:

    items: List[ExtractedMenuItem] = []

    for li in soup.find_all("li"):

        text = clean_text(li.get_text())

        if not text:
            continue

        if is_junk_line(text):
            continue

        price = extract_price(text)

        if price:
            name = extract_name_from_price_line(text, price)
        else:
            name = text

        if not name:
            continue

        items.append(
            ExtractedMenuItem(
                name=name,
                price=price,
            )
        )

    return _dedupe(items)


def detect_menu_cards(soup: BeautifulSoup) -> List[ExtractedMenuItem]:

    items: List[ExtractedMenuItem] = []

    for tag in soup.find_all(True):

        classes = tag.get("class")

        if not classes:
            continue

        class_text = " ".join(classes).lower()

        if not any(c in class_text for c in CARD_CLASSES):
            continue

        text = clean_text(tag.get_text())

        if not text:
            continue

        if is_junk_line(text):
            continue

        price = extract_price(text)

        if price:
            name = extract_name_from_price_line(text, price)
        else:
            name = text

        if not name:
            continue

        items.append(
            ExtractedMenuItem(
                name=name,
                price=price,
            )
        )

    return _dedupe(items)


def detect_price_anchor_items(soup: BeautifulSoup) -> List[ExtractedMenuItem]:

    items: List[ExtractedMenuItem] = []

    for node in soup.find_all(string=True):

        text = clean_text(node)

        if not text:
            continue

        if is_junk_line(text):
            continue

        if not PRICE_REGEX.search(text):
            continue

        price = extract_price(text)

        if not price:
            continue

        name = extract_name_from_price_line(text, price)

        if not name:
            continue

        items.append(
            ExtractedMenuItem(
                name=name,
                price=price,
            )
        )

    return _dedupe(items)


def detect_fallback_items(soup: BeautifulSoup) -> List[ExtractedMenuItem]:

    items: List[ExtractedMenuItem] = []

    for tag in soup.find_all(["p", "div", "span"]):

        text = clean_text(tag.get_text())

        if not text:
            continue

        if is_junk_line(text):
            continue

        if extract_price(text):
            continue

        if len(text) > 60:
            continue

        items.append(
            ExtractedMenuItem(
                name=text,
                price=None,
            )
        )

    return _dedupe(items)