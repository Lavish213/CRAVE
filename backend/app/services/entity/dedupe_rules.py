from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Optional, Tuple


FUZZY_THRESHOLD = 0.86
ADDRESS_FUZZY_THRESHOLD = 0.90
HIGH_CONFIDENCE = 0.92


_CHAIN_STOPWORDS = {
    "restaurant","grill","kitchen","cafe","coffee","bar","bistro",
    "taqueria","pizzeria","pizza","bbq","foods","food","eatery",
    "diner","house","shop","spot","express","market",
}


_NAME_EQUIVALENTS = {
    "&": "and",
    "n'": "and",
    "n": "and",
}


_ADDRESS_EQUIVALENTS = {
    "street": "st","st.": "st",
    "avenue": "ave","ave.": "ave",
    "road": "rd","rd.": "rd",
    "boulevard": "blvd","blvd.": "blvd",
    "drive": "dr","dr.": "dr",
    "lane": "ln","ln.": "ln",
    "court": "ct","ct.": "ct",
    "place": "pl","pl.": "pl",
    "terrace": "ter","ter.": "ter",
    "parkway": "pkwy","highway": "hwy",
    "suite": "ste","unit": "unit",
    "north": "n","south": "s","east": "e","west": "w",
}


# =========================================================
# CORE NORMALIZATION
# =========================================================

def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _clean_basic(value: Optional[str]) -> Optional[str]:

    if not value:
        return None

    value = _strip_accents(value.lower().strip())
    value = value.replace("’", "'").replace("&", " and ")

    value = re.sub(r"[^\w\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()

    return value or None


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


# =========================================================
# NAME
# =========================================================

def _normalize_name(value: Optional[str]) -> Optional[str]:

    cleaned = _clean_basic(value)
    if not cleaned:
        return None

    tokens = []
    for t in cleaned.split():
        tokens.append(_NAME_EQUIVALENTS.get(t, t))

    return " ".join(tokens)


def _brand_core(value: Optional[str]) -> Optional[str]:

    normalized = _normalize_name(value)
    if not normalized:
        return None

    tokens = [t for t in normalized.split() if t not in _CHAIN_STOPWORDS]

    return " ".join(tokens) if tokens else normalized


# =========================================================
# ADDRESS
# =========================================================

def _normalize_address(value: Optional[str]) -> Optional[str]:

    cleaned = _clean_basic(value)
    if not cleaned:
        return None

    tokens = []
    for t in cleaned.split():
        tokens.append(_ADDRESS_EQUIVALENTS.get(t, t))

    return " ".join(tokens)


def _extract_number(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    m = re.search(r"\b\d{1,6}\b", value)
    return m.group(0) if m else None


# =========================================================
# GEO (CRITICAL)
# =========================================================

def _geo_distance_m(lat1, lng1, lat2, lng2):

    if None in (lat1, lng1, lat2, lng2):
        return None

    # fast approximation (good enough for dedupe)
    dx = (lng1 - lng2) * 111320
    dy = (lat1 - lat2) * 110540

    return (dx * dx + dy * dy) ** 0.5


# =========================================================
# MATCH SCORING
# =========================================================

def compute_match_score(
    *,
    name_a: Optional[str],
    name_b: Optional[str],
    addr_a: Optional[str] = None,
    addr_b: Optional[str] = None,
    lat_a: Optional[float] = None,
    lng_a: Optional[float] = None,
    lat_b: Optional[float] = None,
    lng_b: Optional[float] = None,
) -> float:

    score = 0.0

    # ---------------- NAME ----------------
    n1 = _normalize_name(name_a)
    n2 = _normalize_name(name_b)

    if n1 and n2:

        if n1 == n2:
            score += 0.5

        else:
            sim = _similar(n1, n2)
            score += sim * 0.5

        # brand core boost
        b1 = _brand_core(n1)
        b2 = _brand_core(n2)

        if b1 and b2:
            if b1 == b2:
                score += 0.2
            else:
                score += _similar(b1, b2) * 0.2

    # ---------------- ADDRESS ----------------
    a1 = _normalize_address(addr_a)
    a2 = _normalize_address(addr_b)

    if a1 and a2:

        if a1 == a2:
            score += 0.3
        else:
            sim = _similar(a1, a2)
            score += sim * 0.3

        # number mismatch = strong penalty
        num1 = _extract_number(a1)
        num2 = _extract_number(a2)

        if num1 and num2 and num1 != num2:
            score -= 0.4

    # ---------------- GEO ----------------
    dist = _geo_distance_m(lat_a, lng_a, lat_b, lng_b)

    if dist is not None:
        if dist < 30:
            score += 0.3
        elif dist < 100:
            score += 0.2
        elif dist < 300:
            score += 0.1
        else:
            score -= 0.3

    return max(0.0, min(1.0, score))


# =========================================================
# FINAL DECISION
# =========================================================

def is_same_place(
    *,
    name_a: Optional[str],
    name_b: Optional[str],
    addr_a: Optional[str] = None,
    addr_b: Optional[str] = None,
    lat_a: Optional[float] = None,
    lng_a: Optional[float] = None,
    lat_b: Optional[float] = None,
    lng_b: Optional[float] = None,
) -> Tuple[bool, float]:

    score = compute_match_score(
        name_a=name_a,
        name_b=name_b,
        addr_a=addr_a,
        addr_b=addr_b,
        lat_a=lat_a,
        lng_a=lng_a,
        lat_b=lat_b,
        lng_b=lng_b,
    )

    return score >= FUZZY_THRESHOLD, score


# =========================================================
# PUBLIC BOOLEAN HELPERS (used by entity_matcher)
# =========================================================

def names_match(name_a: Optional[str], name_b: Optional[str]) -> bool:
    """
    Return True when two place names are similar enough to be the same entity.
    Uses normalized fuzzy comparison against FUZZY_THRESHOLD.
    """
    n1 = _normalize_name(name_a)
    n2 = _normalize_name(name_b)

    if not n1 or not n2:
        return False

    if n1 == n2:
        return True

    return _similar(n1, n2) >= FUZZY_THRESHOLD


def addresses_match(addr_a: Optional[str], addr_b: Optional[str]) -> bool:
    """
    Return True when two address strings are similar enough to be the same location.
    Uses normalized fuzzy comparison against ADDRESS_FUZZY_THRESHOLD.
    """
    a1 = _normalize_address(addr_a)
    a2 = _normalize_address(addr_b)

    if not a1 or not a2:
        return False

    if a1 == a2:
        return True

    # street number mismatch is a hard disqualifier
    num1 = _extract_number(a1)
    num2 = _extract_number(a2)

    if num1 and num2 and num1 != num2:
        return False

    return _similar(a1, a2) >= ADDRESS_FUZZY_THRESHOLD