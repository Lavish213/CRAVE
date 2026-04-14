from __future__ import annotations

from typing import Optional, Tuple, List

from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.services.query.search_query import search_places
from app.services.search.search_ranker import rank_search_results


def execute_search(
    db: Session,
    *,
    query: str,
    city_id: str,
    category_id: Optional[str] = None,
    price_tier: Optional[int] = None,
    limit: int = 20,
    offset: int = 0,
) -> Tuple[List[Place], int]:
    """
    Execute a place search and apply post-query ranking.

    Returns (places, total_count).
    """

    places, total = search_places(
        db,
        query=query,
        city_id=city_id,
        category_id=category_id,
        price_tier=price_tier,
        limit=limit,
        offset=offset,
    )

    ranked = rank_search_results(list(places), query=query)

    return ranked, total
