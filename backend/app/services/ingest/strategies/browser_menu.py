from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from playwright.sync_api import sync_playwright


logger = logging.getLogger(__name__)


MIN_TEXT_LENGTH = 200


PRICE_REGEX = re.compile(r"\$?\d+(?:\.\d{1,2})")


CATEGORY_KEYWORDS = [
    "appetizers",
    "starters",
    "salads",
    "entrees",
    "mains",
    "sandwiches",
    "burgers",
    "pizza",
    "drinks",
    "beverages",
    "desserts",
    "sides",
]


JUNK_TOKENS = [
    "login",
    "sign up",
    "checkout",
    "cart",
    "privacy",
    "terms",
]


def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def _is_junk(line: str) -> bool:
    lower = line.lower()
    return any(token in lower for token in JUNK_TOKENS)


def _is_category(line: str) -> bool:
    lower = line.lower()

    if len(line) > 40:
        return False

    if any(k in lower for k in CATEGORY_KEYWORDS):
        return True

    if line.isupper() and len(line.split()) <= 5:
        return True

    return False


def _extract_price(line: str) -> float | None:
    match = PRICE_REGEX.search(line)
    if not match:
        return None

    try:
        return float(match.group().replace("$", ""))
    except Exception:
        return None


def _extract_items(text: str) -> List[Dict[str, Any]]:
    lines = [_clean_line(l) for l in text.split("\n") if _clean_line(l)]

    categories: List[Dict[str, Any]] = []
    current_category: Dict[str, Any] = {"name": "Menu", "items": []}

    for i, line in enumerate(lines):
        if _is_junk(line):
            continue

        if _is_category(line):
            if current_category["items"]:
                categories.append(current_category)

            current_category = {
                "name": line.title(),
                "items": [],
            }
            continue

        price = _extract_price(line)

        if price is None:
            continue

        name = line

        if len(name) > 120:
            continue

        item = {
            "name": name,
            "price": price,
        }

        current_category["items"].append(item)

    if current_category["items"]:
        categories.append(current_category)

    return categories


def _flatten(categories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for c in categories:
        for i in c["items"]:
            out.append(i)
    return out


def _is_valid(categories: List[Dict[str, Any]]) -> bool:
    items = _flatten(categories)

    if len(items) < 5:
        return False

    return True


def run(url: str) -> Dict[str, Any]:
    logger.info("BROWSER_MENU_START url=%s", url)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto(url, timeout=60000)

            page.wait_for_timeout(5000)

            for _ in range(6):
                page.mouse.wheel(0, 4000)
                page.wait_for_timeout(800)

            text = page.inner_text("body")

        finally:
            browser.close()

    if not text or len(text) < MIN_TEXT_LENGTH:
        logger.warning("BROWSER_MENU_EMPTY url=%s", url)
        raise RuntimeError("browser_empty")

    categories = _extract_items(text)

    if not _is_valid(categories):
        logger.warning("BROWSER_MENU_INVALID url=%s", url)
        raise RuntimeError("browser_invalid_menu")

    total_items = sum(len(c["items"]) for c in categories)

    logger.info(
        "BROWSER_MENU_SUCCESS url=%s categories=%s items=%s",
        url,
        len(categories),
        total_items,
    )

    return {
        "provider": "browser",
        "url": url,
        "categories": categories,
        "items": _flatten(categories),
    }