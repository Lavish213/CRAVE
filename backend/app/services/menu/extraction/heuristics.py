from __future__ import annotations

import re
import logging
from typing import Iterable, List, Optional
from bs4 import Tag


logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Limits
# -------------------------------------------------------------------

MAX_CONTAINER_SCAN = 8000
MAX_TEXT_LENGTH = 220


# -------------------------------------------------------------------
# Menu container detection
# -------------------------------------------------------------------

MENU_CONTAINER_KEYWORDS = {
    "menu",
    "menu-item",
    "menu-items",
    "menu-section",
    "menu-list",
    "menu-group",
    "menu-category",
    "food-menu",
    "restaurant-menu",
    "food-item",
    "dish",
    "dishes",
    "menu-card",
    "menu-block",
    "menu-wrapper",
    "menu-container",
    "menu-grid",
    "food-list",
    "menu-panel",
    "menu-row",
    "menu-column",
    "menu-entry",
    "menu-cell",
    "menu-table",
}


STRUCTURAL_MENU_TAGS = {
    "section",
    "article",
    "table",
    "ul",
    "ol",
    "div",
}


# -------------------------------------------------------------------
# Junk filtering
# -------------------------------------------------------------------

JUNK_KEYWORDS = {
    "tax",
    "delivery",
    "delivery fee",
    "service charge",
    "service fee",
    "tip",
    "gift card",
    "giftcard",
    "catering",
    "order online",
    "view menu",
    "add to cart",
    "add-to-cart",
    "subscribe",
    "newsletter",
    "privacy policy",
    "terms of service",
    "copyright",
    "all rights reserved",
    "select option",
    "choose option",
}


NAVIGATION_WORDS = {
    "home",
    "about",
    "contact",
    "location",
    "locations",
    "login",
    "sign in",
    "register",
    "account",
    "menu",
    "cart",
    "checkout",
}


# -------------------------------------------------------------------
# Food vocabulary signal
# -------------------------------------------------------------------

FOOD_WORD_HINTS = {
    "burger",
    "pizza",
    "taco",
    "salad",
    "sandwich",
    "fries",
    "chicken",
    "beef",
    "pork",
    "rice",
    "noodle",
    "soup",
    "ramen",
    "sushi",
    "roll",
    "pasta",
    "steak",
    "shrimp",
    "fish",
    "curry",
    "dumpling",
    "bbq",
    "burrito",
    "quesadilla",
    "nachos",
    "pho",
    "omelet",
    "pancake",
    "waffle",
    "dessert",
    "cake",
    "pie",
    "ice cream",
    "milkshake",
    "latte",
    "espresso",
    "mocha",
    "tea",
    "smoothie",
}


# -------------------------------------------------------------------
# Section keywords
# -------------------------------------------------------------------

SECTION_KEYWORDS = {
    "appetizer",
    "appetizers",
    "starter",
    "starters",
    "salad",
    "salads",
    "soup",
    "soups",
    "entree",
    "entrees",
    "main",
    "mains",
    "pizza",
    "burgers",
    "sandwiches",
    "tacos",
    "dessert",
    "desserts",
    "drinks",
    "beverages",
    "cocktails",
    "beer",
    "wine",
}


# -------------------------------------------------------------------
# Price detection
# -------------------------------------------------------------------

PRICE_REGEX = re.compile(
    r"(?:[\$€£]\s?\d{1,4}(?:[\.,]\d{1,2})?)|(?:\d{1,4}(?:[\.,]\d{1,2})?\s?[\$€£])"
)

PRICE_RANGE_REGEX = re.compile(
    r"[\$€£]?\s?\d{1,4}(?:[\.,]\d{1,2})?\s?-\s?[\$€£]?\s?\d{1,4}(?:[\.,]\d{1,2})?"
)


# -------------------------------------------------------------------
# Text helpers
# -------------------------------------------------------------------

_SPACE_RE = re.compile(r"\s+")


def clean_text(text: Optional[str]) -> str:

    if not text:
        return ""

    text = text.strip()
    text = _SPACE_RE.sub(" ", text)

    return text


# -------------------------------------------------------------------
# Junk detection
# -------------------------------------------------------------------

def is_junk_line(text: str) -> bool:

    if not text:
        return True

    lower = text.lower()

    if len(text) > MAX_TEXT_LENGTH:
        return True

    if lower in NAVIGATION_WORDS:
        return True

    for keyword in JUNK_KEYWORDS:
        if keyword in lower:
            return True

    if text.isdigit():
        return True

    return False


# -------------------------------------------------------------------
# Food signal detection
# -------------------------------------------------------------------

def contains_food_signal(name: str) -> bool:

    if not name:
        return False

    lower = name.lower()

    for word in FOOD_WORD_HINTS:
        if word in lower:
            return True

    return False


# -------------------------------------------------------------------
# Price extraction
# -------------------------------------------------------------------

def extract_price(text: str) -> Optional[str]:

    if not text:
        return None

    range_match = PRICE_RANGE_REGEX.search(text)

    if range_match:
        price = range_match.group().strip()
        if any(c.isdigit() for c in price):
            return price

    match = PRICE_REGEX.search(text)

    if not match:
        return None

    price = match.group().strip()

    if not any(c.isdigit() for c in price):
        return None

    if price in {"$0", "0", "0.00", "$0.00"}:
        return None

    return price


# -------------------------------------------------------------------
# Menu container detection
# -------------------------------------------------------------------

def _tag_attrs(tag: Tag) -> str:

    attrs: List[str] = []

    try:

        if tag.get("class"):
            attrs.extend(tag.get("class"))

        if tag.get("id"):
            attrs.append(tag.get("id"))

        if tag.get("role"):
            attrs.append(tag.get("role"))

        for key in tag.attrs.keys():
            if key.startswith("data-"):
                attrs.append(key)

    except Exception:
        return ""

    return " ".join(attrs).lower()


def _container_score(tag: Tag) -> int:

    score = 0

    attr_text = _tag_attrs(tag)

    for keyword in MENU_CONTAINER_KEYWORDS:
        if keyword in attr_text:
            score += 3

    if tag.name in STRUCTURAL_MENU_TAGS:
        score += 1

    text = tag.get_text(" ", strip=True)

    if text:
        lower = text.lower()

        for word in FOOD_WORD_HINTS:
            if word in lower:
                score += 1
                break

    return score


def detect_menu_containers(soup) -> List[Tag]:

    containers: List[tuple[int, Tag]] = []

    scanned = 0

    for tag in soup.find_all(True):

        scanned += 1

        if scanned > MAX_CONTAINER_SCAN:
            logger.debug("menu_container_scan_limit_hit")
            break

        score = _container_score(tag)

        if score >= 3:
            containers.append((score, tag))

    containers.sort(key=lambda x: x[0], reverse=True)

    result = [tag for _, tag in containers]

    if not result:
        result = [soup]

    return result[:10]


# -------------------------------------------------------------------
# Section header detection
# -------------------------------------------------------------------

SECTION_TAGS = {
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "strong",
    "b",
}


def extract_section_headers(node) -> Optional[str]:

    if not isinstance(node, Tag):
        return None

    if node.name not in SECTION_TAGS:
        return None

    text = clean_text(node.get_text())

    if not text:
        return None

    if len(text) > 70:
        return None

    lower = text.lower()

    if lower in SECTION_KEYWORDS:
        return text

    if any(word in lower for word in SECTION_KEYWORDS):
        return text

    if text.isupper():
        return text

    return None


# -------------------------------------------------------------------
# Name extraction helper
# -------------------------------------------------------------------

def extract_name_from_price_line(text: str, price: str) -> Optional[str]:

    if not text:
        return None

    name = text.replace(price, "")

    name = name.replace("-", " ")
    name = name.replace(":", " ")
    name = name.replace("|", " ")

    name = clean_text(name)

    if len(name) < 2:
        return None

    if name.lower() in NAVIGATION_WORDS:
        return None

    return name


# -------------------------------------------------------------------
# Table row extraction helper
# -------------------------------------------------------------------

def extract_table_row_item(row: Tag):

    if row.name != "tr":
        return None

    cells = row.find_all(["td", "th"])

    if len(cells) < 2:
        return None

    name = clean_text(cells[0].get_text())
    price = extract_price(clean_text(cells[-1].get_text()))

    if not name or not price:
        return None

    return name, price


# -------------------------------------------------------------------
# Deduplication helper
# -------------------------------------------------------------------

def dedupe_items(items: Iterable):

    seen = set()
    unique = []

    for item in items:

        name = getattr(item, "name", "") or ""
        price = getattr(item, "price", None)
        section = getattr(item, "section", None)

        key = (
            name.lower().strip(),
            price,
            (section or "").lower().strip(),
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(item)

    return unique