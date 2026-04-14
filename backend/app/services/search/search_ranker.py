from __future__ import annotations

from typing import List

from app.db.models.place import Place


def rank_search_results(places: List[Place], *, query: str = "") -> List[Place]:
    """
    Re-rank search results post-query.

    Primary sort: rank_score descending.
    Secondary: has_menu (places with menus rank higher at equal score).
    Tertiary: name alphabetical (stable tie-break).
    """

    q = (query or "").strip().lower()

    def sort_key(p: Place):
        # Exact name match boost
        name_lower = (p.name or "").lower()
        exact_match = name_lower == q
        starts_with = name_lower.startswith(q) if q else False

        rank = p.rank_score or 0.0
        menu_boost = 0.05 if p.has_menu else 0.0
        exact_boost = 0.10 if exact_match else (0.05 if starts_with else 0.0)

        return (-(rank + menu_boost + exact_boost), p.name or "")

    return sorted(places, key=sort_key)
