from __future__ import annotations

from typing import List, Optional

from app.db.models.place import Place


def rank_search_results(
    places: List[Place],
    *,
    query: str = "",
    lat: Optional[float] = None,
    lng: Optional[float] = None,
) -> List[Place]:
    """
    Re-rank search results post-query.

    Scoring (higher = better):
    - rank_score: base quality [0.07–0.50]
    - exact_boost: +0.10 exact name match, +0.05 prefix match
    - menu_boost: +0.05 if has_menu
    - prox_score: up to +0.15 proximity bonus when lat/lng provided
      formula: 0.15 / (1 + dist_sq * 100)
      — gives ~0.15 at 0km, ~0.05 at 10km, ~0.007 at 50km
    """
    q = (query or "").strip().lower()
    has_location = lat is not None and lng is not None

    def sort_key(p: Place):
        name_lower = (p.name or "").lower()
        exact_match = name_lower == q
        starts_with = name_lower.startswith(q) if q else False

        rank = p.rank_score or 0.0
        menu_boost = 0.05 if p.has_menu else 0.0
        exact_boost = 0.10 if exact_match else (0.05 if starts_with else 0.0)

        prox_score = 0.0
        if has_location and p.lat is not None and p.lng is not None:
            dist_sq = (p.lat - lat) ** 2 + (p.lng - lng) ** 2  # type: ignore[operator]
            prox_score = 0.15 / (1.0 + dist_sq * 100.0)

        total = rank + menu_boost + exact_boost + prox_score
        return (-total, p.name or "")

    return sorted(places, key=sort_key)
