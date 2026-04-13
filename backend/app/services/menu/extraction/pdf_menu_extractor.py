from __future__ import annotations

import io
import logging
import re
from typing import List, Set, Optional

from pdfminer.high_level import extract_text

from app.services.network.http_fetcher import fetch
from app.services.menu.contracts import ExtractedMenuItem


logger = logging.getLogger(__name__)


MAX_PDF_BYTES = 8 * 1024 * 1024
MAX_ITEMS = 1500


PRICE_PATTERN = re.compile(
    r"\$?\s?(\d{1,3}(?:[\.,]\d{2})?)"
)


LINE_ITEM_PATTERN = re.compile(
    r"^(?P<name>[A-Za-z0-9\s\-\&\'\(\)\.,\/\+\!\:]+?)\s+(\$?\d{1,3}(?:[\.,]\d{2})?)$"
)


DOT_PRICE_PATTERN = re.compile(
    r"^(?P<name>.+?)\s*\.{2,}\s*(?P<price>\$?\d{1,3}(?:[\.,]\d{2})?)$"
)


TRAILING_PRICE_PATTERN = re.compile(
    r"(?P<name>.+?)\s+(?P<price>\$?\d{1,3}(?:[\.,]\d{2})?)$"
)


# ---------------------------------------------------------
# Download PDF
# ---------------------------------------------------------

def _download_pdf(url: str) -> bytes:

    response = fetch(url, method="GET")

    if response.status_code != 200:
        raise RuntimeError(f"pdf_fetch_failed status={response.status_code}")

    data = response.content

    if not data:
        raise RuntimeError("empty_pdf")

    if len(data) > MAX_PDF_BYTES:
        raise RuntimeError("pdf_too_large")

    return data


# ---------------------------------------------------------
# Extract text
# ---------------------------------------------------------

def _extract_text(data: bytes) -> str:

    with io.BytesIO(data) as buffer:

        try:
            text = extract_text(buffer)
        except Exception as exc:

            logger.debug(
                "pdf_text_extract_failed error=%s",
                exc,
            )

            return ""

    return text


# ---------------------------------------------------------
# Price cleanup
# ---------------------------------------------------------

def _normalize_price(price: str) -> Optional[str]:

    if not price:
        return None

    try:

        price = price.replace("$", "").strip()

        if not price:
            return None

        return price

    except Exception:
        return None


# ---------------------------------------------------------
# Section detection
# ---------------------------------------------------------

def _detect_section(line: str) -> Optional[str]:

    if len(line) > 50:
        return None

    if PRICE_PATTERN.search(line):
        return None

    words = line.split()

    if len(words) > 5:
        return None

    if line.isupper():
        return line.title()

    if line.istitle() and len(words) <= 4:
        return line

    return None


# ---------------------------------------------------------
# Dedupe
# ---------------------------------------------------------

def _dedupe(items: List[ExtractedMenuItem]) -> List[ExtractedMenuItem]:

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

        if len(unique) >= MAX_ITEMS:
            break

    return unique


# ---------------------------------------------------------
# Parse menu items
# ---------------------------------------------------------

def _parse_lines(text: str) -> List[ExtractedMenuItem]:

    items: List[ExtractedMenuItem] = []

    lines = text.splitlines()

    current_section: Optional[str] = None

    for raw in lines:

        line = raw.strip()

        if not line:
            continue


        # -------------------------------------------------
        # Section headers
        # -------------------------------------------------

        section = _detect_section(line)

        if section:

            current_section = section
            continue


        # -------------------------------------------------
        # Standard pattern
        # -------------------------------------------------

        match = LINE_ITEM_PATTERN.search(line)

        if match:

            name = match.group("name").strip()
            price = match.group(2)

        else:

            # dotted menus
            dotted = DOT_PRICE_PATTERN.search(line)

            if dotted:

                name = dotted.group("name").strip()
                price = dotted.group("price")

            else:

                trailing = TRAILING_PRICE_PATTERN.search(line)

                if trailing:

                    name = trailing.group("name").strip()
                    price = trailing.group("price")

                else:
                    continue


        if not name:
            continue


        price = _normalize_price(price)


        items.append(
            ExtractedMenuItem(
                name=name,
                price=price,
                section=current_section,
                currency="USD",
            )
        )


        if len(items) >= MAX_ITEMS:
            break


    return items


# ---------------------------------------------------------
# Main extractor
# ---------------------------------------------------------

def extract_pdf_menu(url: str) -> List[ExtractedMenuItem]:

    try:

        pdf_data = _download_pdf(url)

        text = _extract_text(pdf_data)

        if not text:
            return []

        items = _parse_lines(text)

        items = _dedupe(items)

        if items:

            logger.info(
                "pdf_menu_extracted url=%s items=%s",
                url,
                len(items),
            )

        return items


    except Exception as exc:

        logger.debug(
            "pdf_menu_failed url=%s error=%s",
            url,
            exc,
        )

        return []