from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.services.scoring.recompute import recompute_place_scores


def compute_master_scores_for_places(
    db: Session,
    places: Iterable[Place],
) -> int:
    """
    Compute and persist master_score + rank_score for the given places.

    Delegates to recompute_place_scores. Does NOT commit — caller must commit.

    Returns the number of places updated.
    """
    return recompute_place_scores(db, places=places)


def compute_master_scores_for_city(
    db: Session,
    city_id: str,
    *,
    active_only: bool = True,
) -> int:
    """
    Recompute scores for all places in a city.

    Commits after each batch of 200.
    Returns total places updated.
    """
    from sqlalchemy import select

    stmt = select(Place).where(Place.city_id == city_id)
    if active_only:
        stmt = stmt.where(Place.is_active.is_(True))

    places = list(db.execute(stmt).scalars().all())
    updated = recompute_place_scores(db, places=places)
    db.commit()
    return updated
