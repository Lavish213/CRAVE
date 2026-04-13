from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from app.db.models.place import Place
from app.db.models.category import Category


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlaceCard:
    id: str
    name: str
    city_id: str

    lat: Optional[float]
    lng: Optional[float]

    price_tier: Optional[int]

    rank_score: float
    master_score: float
    confidence_score: float
    operational_confidence: float
    local_validation: float

    primary_image: Optional[str]

    categories: List[str]


def _ordered_category_names(categories: Sequence[Category]) -> List[str]:
    if not categories:
        return []

    try:
        ordered = sorted(
            categories,
            key=lambda c: ((getattr(c, "name", "") or "").lower(), getattr(c, "id", "")),
        )

        names: List[str] = []
        seen: set[str] = set()

        for c in ordered:
            name = (getattr(c, "name", "") or "").strip()

            if not name or name in seen:
                continue

            seen.add(name)
            names.append(name)

        return names

    except Exception as exc:
        logger.debug("category_ordering_failed error=%s", exc)
        return []


def _safe_float(value: object) -> float:
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def build_place_card(
    *,
    place: Place,
    primary_image_url: Optional[str],
    categories: Sequence[Category],
) -> PlaceCard:
    try:
        return PlaceCard(
            id=getattr(place, "id", ""),
            name=getattr(place, "name", ""),
            city_id=getattr(place, "city_id", ""),
            lat=getattr(place, "lat", None),
            lng=getattr(place, "lng", None),
            price_tier=getattr(place, "price_tier", None),
            rank_score=_safe_float(getattr(place, "rank_score", 0.0)),
            master_score=_safe_float(getattr(place, "master_score", 0.0)),
            confidence_score=_safe_float(getattr(place, "confidence_score", 0.0)),
            operational_confidence=_safe_float(getattr(place, "operational_confidence", 0.0)),
            local_validation=_safe_float(getattr(place, "local_validation", 0.0)),
            primary_image=primary_image_url,
            categories=_ordered_category_names(categories),
        )

    except Exception as exc:
        logger.exception(
            "build_place_card_failed place_id=%s error=%s",
            getattr(place, "id", None),
            exc,
        )

        # safe fallback card
        return PlaceCard(
            id=getattr(place, "id", ""),
            name=getattr(place, "name", ""),
            city_id=getattr(place, "city_id", ""),
            lat=None,
            lng=None,
            price_tier=None,
            rank_score=0.0,
            master_score=0.0,
            confidence_score=0.0,
            operational_confidence=0.0,
            local_validation=0.0,
            primary_image=None,
            categories=[],
        )


def build_place_cards_bulk(
    *,
    places: Sequence[Place],
    image_map: Dict[str, str],
    category_map: Dict[str, List[Category]],
) -> List[PlaceCard]:
    if not places:
        return []

    cards: List[PlaceCard] = []

    for place in places:
        try:
            place_id = getattr(place, "id", None)

            card = build_place_card(
                place=place,
                primary_image_url=image_map.get(place_id),
                categories=category_map.get(place_id, []),
            )

            cards.append(card)

        except Exception as exc:
            logger.debug(
                "build_place_cards_bulk_item_failed place_id=%s error=%s",
                getattr(place, "id", None),
                exc,
            )
            continue

    return cards