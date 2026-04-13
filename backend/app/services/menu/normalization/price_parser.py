from __future__ import annotations

import re
from typing import Optional, Tuple, Any


# ---------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------

PRICE_REGEX = re.compile(r"\d+(?:[.,]\d{1,2})?")
CURRENCY_SYMBOL_REGEX = re.compile(r"[\$€£]")
CURRENCY_CODE_REGEX = re.compile(r"\b(USD|EUR|GBP)\b", re.IGNORECASE)


# ---------------------------------------------------------
# Currency mapping
# ---------------------------------------------------------

CURRENCY_MAP = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
}


# ---------------------------------------------------------
# Normalize number string → float
# ---------------------------------------------------------

def _parse_number(value: str) -> Optional[float]:
    if not value:
        return None

    try:
        # 🔥 fix: handle thousands properly
        value = value.replace(",", "")
        return float(value)
    except Exception:
        return None


# ---------------------------------------------------------
# Convert to cents
# ---------------------------------------------------------

def _to_cents(value: float) -> int:
    return int(round(value * 100))


# ---------------------------------------------------------
# Extract currency
# ---------------------------------------------------------

def _extract_currency(text: str) -> Optional[str]:

    # symbol first
    symbol_match = CURRENCY_SYMBOL_REGEX.search(text)
    if symbol_match:
        return CURRENCY_MAP.get(symbol_match.group(0))

    # code fallback
    code_match = CURRENCY_CODE_REGEX.search(text)
    if code_match:
        return code_match.group(1).upper()

    return None


# ---------------------------------------------------------
# Handle dict-style prices
# ---------------------------------------------------------

def _handle_dict_price(value: Any) -> Optional[Tuple[int, Optional[str]]]:

    if not isinstance(value, dict):
        return None

    for key in ("amount", "value", "price"):
        if key in value:
            parsed = parse_price(value[key])
            if parsed and parsed[0] is not None:
                return parsed

    return None


# ---------------------------------------------------------
# Handle numeric
# ---------------------------------------------------------

def _handle_numeric(value: Any) -> Optional[Tuple[int, Optional[str]]]:

    if isinstance(value, (int, float)):

        number = float(value)

        if number <= 0:
            return None

        # 🔥 safer heuristic
        if number > 10_000:  # clearly cents
            return int(number), None

        return _to_cents(number), None

    return None


# ---------------------------------------------------------
# Handle string
# ---------------------------------------------------------

def _handle_string(value: str) -> Optional[Tuple[int, Optional[str]]]:

    text = value.strip()

    if not text:
        return None

    currency = _extract_currency(text)

    # ---------------------------------------------------------
    # Range handling (take first)
    # ---------------------------------------------------------

    if "-" in text:
        text = text.split("-")[0].strip()

    # ---------------------------------------------------------
    # Extract number
    # ---------------------------------------------------------

    match = PRICE_REGEX.search(text)

    if not match:
        return None

    number = _parse_number(match.group(0))

    if number is None or number <= 0:
        return None

    cents = _to_cents(number)

    # 🔥 guard insane values
    if cents > 1_000_000:
        return None

    return cents, currency


# ---------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------

def parse_price(value: Any) -> Tuple[Optional[int], Optional[str]]:
    """
    Returns:
        (price_cents, currency)

    Handles:
    - "$12.99"
    - "12.99 USD"
    - "10 - 15"
    - {"amount": 12.99}
    - 1299 (already cents)
    - None / invalid
    """

    if value is None:
        return None, None

    # ---------------- DICT ----------------
    dict_result = _handle_dict_price(value)
    if dict_result:
        return dict_result

    # ---------------- NUMERIC ----------------
    numeric_result = _handle_numeric(value)
    if numeric_result:
        return numeric_result

    # ---------------- STRING ----------------
    if isinstance(value, str):
        string_result = _handle_string(value)
        if string_result:
            return string_result

    return None, None