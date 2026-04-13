from __future__ import annotations

from typing import List, Set, Optional

from app.db.models.place import Place


DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def _clamp_limit(limit: int) -> int:
    try:
        n = int(limit)
    except Exception:
        return DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, n))


def _category_key(place: Place) -> Optional[str]:
    """
    Best-effort category extraction.

    Safe even if relationship is not eagerly loaded.
    """

    try:
        cats = getattr(place, "categories", None)
        if cats:
            c = cats[0]
            return getattr(c, "id", None)
    except Exception:
        pass

    return None


# =========================================================
# Feed Mixer
# =========================================================

def mix_feed(
    *,
    stable_places: List[Place],
    discovery_places: List[Place],
    limit: int,
) -> List[Place]:
    """
    Production feed mixer.

    Feed pattern:
        4 stable
        1 discovery

    Guarantees
    ----------
    • deterministic ordering
    • duplicate protection
    • category diversity guard
    • stable/discovery blending
    • no mutation of inputs
    """

    limit = _clamp_limit(limit)

    if not stable_places and not discovery_places:
        return []

    if not discovery_places:
        return stable_places[:limit]

    if not stable_places:
        return discovery_places[:limit]

    result: List[Place] = []
    seen: Set[str] = set()

    stable_index = 0
    discovery_index = 0

    stable_total = len(stable_places)
    discovery_total = len(discovery_places)

    stable_block = 4

    last_category: Optional[str] = None
    category_streak = 0

    while len(result) < limit:

        # =====================================================
        # Stable block
        # =====================================================

        for _ in range(stable_block):

            if stable_index >= stable_total:
                break

            place = stable_places[stable_index]
            stable_index += 1

            pid = getattr(place, "id", None)

            if not pid or pid in seen:
                continue

            cat = _category_key(place)

            if cat == last_category:
                category_streak += 1
            else:
                category_streak = 1
                last_category = cat

            if category_streak > 2:
                continue

            result.append(place)
            seen.add(pid)

            if len(result) >= limit:
                return result

        # =====================================================
        # Discovery insertion
        # =====================================================

        if discovery_index < discovery_total:

            place = discovery_places[discovery_index]
            discovery_index += 1

            pid = getattr(place, "id", None)

            if not pid or pid in seen:
                continue

            cat = _category_key(place)

            if cat == last_category:
                category_streak += 1
            else:
                category_streak = 1
                last_category = cat

            if category_streak > 2:
                continue

            result.append(place)
            seen.add(pid)

            if len(result) >= limit:
                return result

        # =====================================================
        # Exit guard
        # =====================================================

        if stable_index >= stable_total and discovery_index >= discovery_total:
            break

    return result[:limit]