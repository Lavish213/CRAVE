# FILE: backend/app/services/ingest/csv_menu_ingest.py

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Dict, List, Optional, Iterable, Set

from app.services.menu.contracts import ExtractedMenuItem


logger = logging.getLogger(__name__)

MAX_ITEMS = 2000
DEFAULT_CURRENCY = "USD"


# ---------------------------------------------------------
# COLUMN ALIASES (LOWERCASE MATCHING)
# ---------------------------------------------------------

NAME_FIELDS = ("name", "item_name", "title")
SECTION_FIELDS = ("section", "category", "menu_section")
PRICE_FIELDS = ("price", "cost", "amount")
DESCRIPTION_FIELDS = ("description", "desc", "details")
IMAGE_FIELDS = ("image", "image_url", "img")
CURRENCY_FIELDS = ("currency",)


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def _clean_str(value: object) -> Optional[str]:
    if value is None:
        return None
    try:
        s = str(value).strip()
        return s if s else None
    except Exception:
        return None


def _normalize_row_keys(row: Dict) -> Dict:
    """
    Normalize CSV keys to lowercase for consistent matching.
    """
    return {str(k).lower().strip(): v for k, v in row.items()}


def _get_first(row: Dict, keys: Iterable[str]) -> Optional[str]:
    for key in keys:
        val = _clean_str(row.get(key))
        if val:
            return val
    return None


def _parse_price(value: object) -> Optional[str]:
    """
    Keep as string (pipeline will convert to cents).
    Supports: "$12.99", "12.99", "12"
    """
    if value is None:
        return None

    try:
        s = str(value).strip()
        if not s:
            return None

        # remove symbols
        s = s.replace("$", "").replace(",", "").strip()

        # validate numeric
        float(s)

        return s
    except Exception:
        return None


def _dedupe_key(
    name: Optional[str],
    section: Optional[str],
    price: Optional[str],
) -> Optional[str]:
    if not name:
        return None

    return "|".join(
        [
            name.lower().strip(),
            (section or "").lower().strip(),
            (price or "").strip(),
        ]
    )


# ---------------------------------------------------------
# CORE PARSER
# ---------------------------------------------------------

def parse_csv_rows(
    rows: List[Dict],
    *,
    source_url: Optional[str] = None,
) -> List[ExtractedMenuItem]:

    results: List[ExtractedMenuItem] = []
    seen: Set[str] = set()

    for raw_row in rows:

        if len(results) >= MAX_ITEMS:
            break

        try:
            row = _normalize_row_keys(raw_row)

            name = _get_first(row, NAME_FIELDS)
            if not name:
                continue

            section = _get_first(row, SECTION_FIELDS)
            price = _parse_price(_get_first(row, PRICE_FIELDS))
            description = _get_first(row, DESCRIPTION_FIELDS)
            image_url = _get_first(row, IMAGE_FIELDS)

            currency = (_get_first(row, CURRENCY_FIELDS) or DEFAULT_CURRENCY).upper()

            key = _dedupe_key(name, section, price)
            if key and key in seen:
                continue

            if key:
                seen.add(key)

            item = ExtractedMenuItem(
                name=name,
                price=price,
                section=section,
                currency=currency,
                description=description,
                image_url=image_url,
                provider="csv",
                source_type="csv",
                source_url=source_url,
                raw=raw_row,
            )

            results.append(item)

        except Exception as exc:
            logger.debug("csv_row_failed error=%s row=%s", exc, raw_row)
            continue

    logger.info(
        "csv_parse_complete input=%s output=%s source=%s",
        len(rows),
        len(results),
        source_url,
    )

    return results


# ---------------------------------------------------------
# FILE READER
# ---------------------------------------------------------

def parse_csv_file(file_path: Path) -> List[ExtractedMenuItem]:

    if not file_path.exists():
        logger.error("csv_file_missing path=%s", file_path)
        return []

    rows: List[Dict] = []

    try:
        with file_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)

            for row in reader:
                if not isinstance(row, dict):
                    continue
                rows.append(row)

    except Exception as exc:
        logger.exception("csv_file_read_failed path=%s error=%s", file_path, exc)
        return []

    return parse_csv_rows(rows, source_url=str(file_path))


# ---------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------

def run_ingest(file_path: Path) -> List[ExtractedMenuItem]:
    """
    Main entrypoint for CSV ingestion.
    """
    return parse_csv_file(file_path)