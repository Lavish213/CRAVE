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

from sqlalchemy.exc import IntegrityError
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
_MAX_CLIENT_EVENT_ID_LEN = 64


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
        client_event_id = getattr(e, "client_event_id", None)

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
                client_event_id=(client_event_id or None)[:_MAX_CLIENT_EVENT_ID_LEN] if client_event_id else None,
            )
        )

    return valid


def _drop_already_recorded(db: Session, events: List[RecommendationEvent]) -> List[RecommendationEvent]:
    """
    Filters out events whose client_event_id has already been persisted
    (a resubmission after the process-kill-before-persist race described
    on that column) -- and, within this same batch, keeps only the first
    of any duplicate client_event_id a client mistakenly sent twice.
    Events with no client_event_id (the overwhelming majority --
    impression/click/rank) always pass through untouched.
    """
    ids = [e.client_event_id for e in events if e.client_event_id]
    if not ids:
        return events

    already_recorded = {
        row[0]
        for row in db.query(RecommendationEvent.client_event_id)
        .filter(RecommendationEvent.client_event_id.in_(ids))
        .all()
    }

    seen_in_batch: set = set()
    kept: List[RecommendationEvent] = []
    for e in events:
        if e.client_event_id:
            if e.client_event_id in already_recorded or e.client_event_id in seen_in_batch:
                continue
            seen_in_batch.add(e.client_event_id)
        kept.append(e)
    return kept


def record_events(
    db: Session,
    *,
    raw_events: Iterable,
    user_id: Optional[str],
) -> int:
    """
    Validates, builds, and persists a batch of recommendation events.
    Returns the number actually accepted (<= len(raw_events) -- some may
    have been dropped as malformed or as an already-recorded
    client_event_id resubmission). Caller is responsible for enforcing
    MAX_BATCH_SIZE before calling this (kept separate so it can be a
    normal 422 at the route layer rather than a silent truncation here).
    """
    events = build_valid_events(raw_events=raw_events, user_id=user_id)
    if not events:
        return 0

    events = _drop_already_recorded(db, events)
    if not events:
        return 0

    db.add_all(events)
    try:
        db.commit()
    except IntegrityError:
        # A genuine race lost to a concurrent request inserting the same
        # client_event_id between the pre-check above and this commit
        # (e.g. two flush passes from two devices signed into the same
        # account). The partial unique index is what actually guarantees
        # no duplicate ever lands -- fall back to inserting one at a time
        # so only the entries that actually lost the race get dropped,
        # not the whole batch.
        db.rollback()
        accepted = 0
        for event in events:
            db.add(event)
            try:
                db.commit()
                accepted += 1
            except IntegrityError:
                db.rollback()
        return accepted

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
