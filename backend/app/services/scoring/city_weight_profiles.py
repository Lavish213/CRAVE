# app/services/scoring/city_weight_profiles.py
from __future__ import annotations
from typing import Dict, Optional

SIGNALS = [
    "menu_score", "image_score", "completeness_score", "recency_score",
    "app_score", "hitlist_score", "creator_score", "awards_score", "blog_score",
]

DEFAULT_PROFILE: Dict[str, float] = {
    "menu_score":         0.28,  # was 0.22, increased (discriminating: 16% coverage)
    "image_score":        0.15,  # was 0.18, reduced (near-universal: 98% coverage)
    "completeness_score": 0.12,  # unchanged
    "recency_score":      0.10,  # unchanged
    "app_score":          0.19,  # was 0.13, increased (discriminating: 16% coverage)
    "hitlist_score":      0.10,  # unchanged
    "creator_score":      0.01,  # was 0.08, drastically reduced (no data exists)
    "awards_score":       0.03,  # was 0.04, slightly reduced (no data exists)
    "blog_score":         0.02,  # was 0.03, reduced (no data exists)
}  # sums to 1.0

CITY_PROFILES: Dict[str, Dict[str, float]] = {
    "nyc": {
        # Emphasizes awards + blog; app_score reduced to absorb the extra weight
        "menu_score":         0.24,
        "image_score":        0.15,
        "completeness_score": 0.12,
        "recency_score":      0.10,
        "app_score":          0.14,  # reduced vs default to balance elevated awards/blog
        "hitlist_score":      0.10,
        "creator_score":      0.01,
        "awards_score":       0.08,
        "blog_score":         0.06,
    },  # sum = 1.0
    "los_angeles": {
        # Emphasizes creator + hitlist; app_score reduced to absorb
        "menu_score":         0.28,
        "image_score":        0.15,
        "completeness_score": 0.12,
        "recency_score":      0.10,
        "app_score":          0.12,  # reduced vs default to balance elevated creator/hitlist
        "hitlist_score":      0.12,
        "creator_score":      0.08,
        "awards_score":       0.01,
        "blog_score":         0.02,
    },  # sum = 1.0
    "new_orleans": {
        # Emphasizes blog + awards; menu_score reduced to absorb
        "menu_score":         0.24,  # reduced vs default to balance elevated blog/awards/app
        "image_score":        0.15,
        "completeness_score": 0.12,
        "recency_score":      0.10,
        "app_score":          0.16,
        "hitlist_score":      0.10,
        "creator_score":      0.01,
        "awards_score":       0.05,
        "blog_score":         0.07,
    },  # sum = 1.0
}


def _validate_profile(profile: Dict[str, float], name: str) -> None:
    total = sum(profile.values())
    if abs(total - 1.0) > 0.001:
        raise ValueError(f"Profile '{name}' weights sum to {total:.4f}, must be 1.0")
    for sig in SIGNALS:
        if sig not in profile:
            raise ValueError(f"Profile '{name}' is missing signal '{sig}'")


# Validate at import — fail loud if misconfigured
_validate_profile(DEFAULT_PROFILE, "default")
for _slug, _p in CITY_PROFILES.items():
    _validate_profile(_p, _slug)


def get_profile(city_slug: Optional[str]) -> Dict[str, float]:
    if not city_slug:
        return DEFAULT_PROFILE
    normalized = city_slug.lower().strip().replace(" ", "_").replace("-", "_")
    return CITY_PROFILES.get(normalized, DEFAULT_PROFILE)
