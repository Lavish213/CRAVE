from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Optional


# ---------------------------------------------------------
# Regex
# ---------------------------------------------------------

PUNCT_REGEX = re.compile(r"[^\w\s]")
SPACE_REGEX = re.compile(r"\s+")
NUMBER_FRACTION_REGEX = re.compile(r"(\d+)\s*/\s*(\d+)")


# ---------------------------------------------------------
# Stop words (expanded)
# ---------------------------------------------------------

COMMON_WORDS = {
    "the",
    "a",
    "an",
    "and",
    "with",
    "of",
    "for",
    "to",
    "on",
    "in",
    "at",
    "by",
    "from",
    "or",
    "your",
    "our",
    "served",
    "style",
    "fresh",
}


# ---------------------------------------------------------
# Unicode normalization
# ---------------------------------------------------------

def _normalize_unicode(text: str) -> str:
    try:
        text = unicodedata.normalize("NFKD", text)
        text = text.encode("ascii", "ignore").decode("ascii")
    except Exception:
        pass
    return text


# ---------------------------------------------------------
# Number normalization
# ---------------------------------------------------------

def _normalize_numbers(text: str) -> str:
    text = text.replace("½", "0.5")
    text = text.replace("¼", "0.25")
    text = text.replace("¾", "0.75")

    def _convert_fraction(match):
        try:
            num = float(match.group(1))
            den = float(match.group(2))
            return str(round(num / den, 3))
        except Exception:
            return match.group(0)

    return NUMBER_FRACTION_REGEX.sub(_convert_fraction, text)


# ---------------------------------------------------------
# Stop word removal
# ---------------------------------------------------------

def _remove_common_words(tokens: list[str]) -> list[str]:
    return [t for t in tokens if t not in COMMON_WORDS]


# ---------------------------------------------------------
# Plural reduction (safe)
# ---------------------------------------------------------

def _reduce_plural(tokens: list[str]) -> list[str]:
    reduced = []

    for token in tokens:
        if len(token) <= 3:
            reduced.append(token)
            continue

        if token.endswith("ies"):
            reduced.append(token[:-3] + "y")
        elif token.endswith("es"):
            reduced.append(token[:-2])
        elif token.endswith("s"):
            reduced.append(token[:-1])
        else:
            reduced.append(token)

    return reduced


# ---------------------------------------------------------
# Text normalization
# ---------------------------------------------------------

def _normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""

    text = value.strip().lower()

    text = _normalize_unicode(text)
    text = _normalize_numbers(text)

    text = PUNCT_REGEX.sub(" ", text)
    text = SPACE_REGEX.sub(" ", text).strip()

    if not text:
        return ""

    tokens = text.split()

    tokens = _remove_common_words(tokens)
    tokens = _reduce_plural(tokens)

    # 🔥 CRITICAL: stable ordering
    tokens = sorted(tokens)

    return " ".join(tokens)


# ---------------------------------------------------------
# Fingerprint builder (PRIMARY)
# ---------------------------------------------------------

def build_menu_fingerprint(
    name: str,
    section: Optional[str],
    currency: Optional[str],
) -> str:
    """
    Stable identity for menu items.

    IMPORTANT:
    - Price is intentionally excluded
    - This allows price changes without breaking identity
    """

    name_norm = _normalize_text(name)
    section_norm = _normalize_text(section or "")
    currency_norm = _normalize_text(currency or "usd")

    base = f"{name_norm}|{section_norm}|{currency_norm}"

    if not base.strip():
        base = "unknown"

    return hashlib.sha256(base.encode("utf-8")).hexdigest()


# ---------------------------------------------------------
# Debug helper (optional but 🔥 useful)
# ---------------------------------------------------------

def debug_fingerprint_inputs(name: str, section: Optional[str], currency: Optional[str]) -> dict:
    return {
        "name_raw": name,
        "section_raw": section,
        "currency_raw": currency,
        "name_norm": _normalize_text(name),
        "section_norm": _normalize_text(section or ""),
        "currency_norm": _normalize_text(currency or "usd"),
    }