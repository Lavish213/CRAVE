from __future__ import annotations

from typing import List

from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.db.models.city_place_ranking import CityPlaceRanking


def recompute_city_ranking(
    *,
    db: Session,
    city_id: str,
) -> int:
    """
    Recomputes the ranking snapshot for a city.

    Ranking rules (deterministic):
        rank_score DESC
        id ASC

    Steps:
        1) fetch active places
        2) sort deterministically
        3) clear previous ranking snapshot
        4) write new snapshot

    Returns:
        number of ranked places
    """

    # --------------------------------------------------
    # Fetch places
    # --------------------------------------------------

    stmt = (
        select(Place)
        .where(
            Place.city_id == city_id,
            Place.is_active.is_(True),
        )
        .order_by(
            Place.rank_score.desc(),
            Place.id.asc(),
        )
    )

    places: List[Place] = list(db.execute(stmt).scalars().all())

    # --------------------------------------------------
    # Clear old ranking snapshot
    # --------------------------------------------------

    db.execute(
        delete(CityPlaceRanking).where(
            CityPlaceRanking.city_id == city_id
        )
    )

    # --------------------------------------------------
    # Insert new snapshot
    # --------------------------------------------------

    rankings: List[CityPlaceRanking] = []

    position = 1

    for place in places:
        rankings.append(
            CityPlaceRanking(
                city_id=city_id,
                place_id=place.id,
                rank_position=position,
                rank_score=place.rank_score,
            )
        )
        position += 1

    db.add_all(rankings)

    db.commit()

    return len(rankings)