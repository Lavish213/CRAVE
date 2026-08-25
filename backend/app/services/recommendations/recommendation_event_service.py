"""
Recommendation Ledger, phase 1 -- write side. See
app/db/models/recommendation_event.py for the full rationale.

Each event is validated and normalized independently so that one
malformed entry in a client-submitted batch (a typo'd surface, a stray
out-of-range percentile from a client running slightly older code)
doesn't drop the rest of that same batch -- telemetry should degrade by
losing the one bad row, never by losing everything alongside it.
"""
from __future__ import annotations

from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from app.db.models.recommendation_event import (
    EVENT_RANK,
    SURFACE_PLACE_DETAIL,
    VALID_EVENT_TYPES,
    VALID_SURFACES,
    RecommendationEvent,
)

# Hard ceiling on a single batch -- generous enough for a full screen's
# worth of impressions (a Feed page is page_size=40) plus a few
# clicks/saves, but small enough that one runaway client can't turn this
# into an unbounded-insert vector.
MAX_BATCH_SIZE = 200

_MAX_QUERY_LEN = 200
_MAX_SESSION_ID_LEN = 64


def _clamp_percentile(value) -> Optional[float]:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, v))


def build_valid_events(
    *,
    raw_events: Iterable,
    user_id: Optional[str],
) -> List[RecommendationEvent]:
    """
    Validates and normalizes each raw event dict/object, dropping (not
    raising on) anything malformed. `raw_events` items are expected to
    have the same attributes as RecommendationEventIn (see
    app/api/v1/schemas/recommendation_event.py) -- duck-typed rather than
    imported directly so this stays independently unit-testable without
    the FastAPI/Pydantic layer.
    """
    valid: List[RecommendationEvent] = []

    for e in raw_events:
        surface = getattr(e, "surface", None)
        event_type = getattr(e, "event_type", None)

        if surface not in VALID_SURFACES:
            continue
        if event_type not in VALID_EVENT_TYPES:
            continue

        query = getattr(e, "query", None)
        session_id = getattr(e, "session_id", None)

        valid.append(
            RecommendationEvent(
                user_id=user_id,
                session_id=(session_id or None)[:_MAX_SESSION_ID_LEN] if session_id else None,
                place_id=getattr(e, "place_id", None) or None,
                surface=surface,
                event_type=event_type,
                position=getattr(e, "position", None),
                rank_percentile=_clamp_percentile(getattr(e, "rank_percentile", None)),
                query=(query or None)[:_MAX_QUERY_LEN] if query else None,
                city_id=getattr(e, "city_id", None) or None,
            )
        )

    return valid


def record_events(
    db: Session,
    *,
    raw_events: Iterable,
    user_id: Optional[str],
) -> int:
    """
    Validates, builds, and persists a batch of recommendation events.
    Returns the number actually accepted (<= len(raw_events) -- some may
    have been dropped as malformed). Caller is responsible for enforcing
    MAX_BATCH_SIZE before calling this (kept separate so it can be a
    normal 422 at the route layer rather than a silent truncation here).
    """
    events = build_valid_events(raw_events=raw_events, user_id=user_id)
    if not events:
        return 0

    db.add_all(events)
    db.commit()
    return len(events)


def record_rank_outcome(
    db: Session,
    *,
    user_id: str,
    place_id: str,
    city_id: Optional[str] = None,
) -> RecommendationEvent:
    """
    Logs a *completed* personal ranking -- called only from the two
    rankings.py code paths where a ranking actually lands (immediate
    top/bottom placement in start_ranking, or the converging comparison
    in submit_comparison), never per comparison tap, and never on a
    replayed/already-recorded outcome (callers already guard on
    `already_existed` for the same reason record_ranked_place is skipped
    there -- see rankings.py).

    Deliberately doesn't set rank_percentile: that field means "this
    place's city-percentile standing at event time" (see the model's own
    docstring) and a personal ranking's rank_score is a different,
    unrelated signal -- conflating the two would blur exactly the
    percentile-tier-vs-personalization line this app is trying to keep
    separate elsewhere. Matches record_ranked_place's own
    add()-then-let-the-route-commit convention rather than committing
    here itself.
    """
    event = RecommendationEvent(
        user_id=user_id,
        place_id=place_id,
        surface=SURFACE_PLACE_DETAIL,
        event_type=EVENT_RANK,
        city_id=city_id,
    )
    db.add(event)
    db.flush()
    return event
