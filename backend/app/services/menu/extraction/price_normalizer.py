from __future__ import annotations

import re
from typing import Any, Optional


_NUMERIC_PRICE = re.compile(r"-?\d+(?:\.\d+)?")


def coerce_price_cents(value: Any) -> Optional[int]:
    """Normalize common provider/API price shapes to integer cents.

    Integer-like values of 100 or more are treated as cents, matching the
    conventions used by Toast, Clover, Square, and CRAVE hydration payloads.
    Decimal or explicitly currency-formatted values are treated as dollars.
    """

    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, dict):
        for key in ("amount", "price", "value", "unit_amount", "unitAmount"):
            if key in value:
                return coerce_price_cents(value[key])
        return None

    explicitly_dollars = False

    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if not text:
            return None
        explicitly_dollars = any(marker in text for marker in ("$", "USD", "usd"))
        match = _NUMERIC_PRICE.search(text)
        if not match:
            return None
        numeric_text = match.group(0)
        numeric = float(numeric_text)
        has_decimal = "." in numeric_text
    elif isinstance(value, (int, float)):
        numeric = float(value)
        has_decimal = isinstance(value, float) and not value.is_integer()
    else:
        return None

    if numeric < 0:
        return None

    if explicitly_dollars or has_decimal or numeric < 100:
        cents = int(round(numeric * 100))
    else:
        cents = int(round(numeric))

    return cents if cents <= 10_000_000 else None
