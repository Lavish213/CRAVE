from __future__ import annotations

import re
from typing import Optional, Any


# =========================================================
# CATEGORY NORMALIZATION (DB-ALIGNED)
# =========================================================

# 🔥 MUST MATCH seed_categories slugs EXACTLY
_CATEGORY_KEYWORDS = {
    "mexican": ["mexican", "taqueria", "taco", "tacos", "burrito", "burritos"],
    "italian": ["italian", "pasta"],
    "chinese": ["chinese"],
    "japanese": ["japanese", "sushi", "ramen"],
    "korean": ["korean", "bbq korean"],
    "thai": ["thai"],
    "indian": ["indian"],
    "mediterranean": ["mediterranean"],
    "american": ["american", "burger", "burgers", "hamburger"],
    "bbq": ["bbq", "barbecue"],
    "seafood": ["seafood"],
    "pizza": ["pizza", "pizzeria"],
    "breakfast": ["breakfast", "brunch"],
    "coffee": ["coffee", "cafe", "espresso"],
    "desserts": ["dessert", "desserts", "ice cream", "bakery"],
}


def normalize_category(raw: Optional[str]) -> str:
    """
    Maps provider category → VALID DB category slug.
    Always returns a slug that EXISTS in the database.
    """

    if not raw:
        return "other"

    text = raw.lower().strip()
    text = re.sub(r"\s+", " ", text)

    # 🔥 keyword match (contains, not exact)
    for slug, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return slug

    return "other"


# =========================================================
# NUMERIC SAFETY
# =========================================================

def clamp(v: float | None, lo: float = 0.0, hi: float = 1.0) -> float:
    if v is None:
        return lo
    return max(lo, min(hi, float(v)))


def normalize_price(raw: Any) -> Optional[int]:
    """
    Normalize price into integer tier (1-4)
    """
    if raw in (1, "1", "$"):
        return 1
    if raw in (2, "2", "$$"):
        return 2
    if raw in (3, "3", "$$$"):
        return 3
    if raw in (4, "4", "$$$$"):
        return 4
    return None


def normalize_open_status(raw: Any) -> str:
    if not raw:
        return "unknown"

    val = str(raw).lower().strip()

    if val in {"open", "open_now", "true"}:
        return "open"

    if val in {"closed", "false"}:
        return "closed"

    return "unknown"


def normalize_confidence(raw: Any) -> float:
    if raw in ("high", "HIGH", 1, 1.0):
        return 1.0
    if raw in ("medium", "MEDIUM", 0.6):
        return 0.6
    if raw in ("low", "LOW", 0.3):
        return 0.3

    try:
        val = float(raw)
        return clamp(val)
    except Exception:
        return 0.3


# =========================================================
# MASTER RUBRIC (UNCHANGED — ALREADY GOOD)
# =========================================================

def compute_master_score(
    *,
    taste_score: float,
    confidence_score: float,
    operational_confidence: float,
    local_validation: float,
    hype_penalty: float,
) -> tuple[float, float]:

    taste = clamp((taste_score or 0.0) / 5.0)
    confidence = clamp(confidence_score)
    ops = clamp(operational_confidence)
    local = clamp(local_validation)
    hype = clamp(hype_penalty)

    base_quality = (taste * 0.72) + (confidence * 0.28)

    trust = (
        (ops * 0.45) +
        (local * 0.35) +
        (confidence * 0.20)
    )

    trusted_quality = base_quality * (0.75 + 0.25 * trust)

    penalty_multiplier = 1.0 - (hype * 0.35)

    master_score = clamp(trusted_quality * penalty_multiplier)

    confidence_5 = round(confidence * 5.0, 2)

    return round(master_score, 4), confidence_5