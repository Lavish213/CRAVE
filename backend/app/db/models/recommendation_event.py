# app/db/models/recommendation_event.py
"""
Recommendation Ledger, phase 1.

Every place a user is shown, and what they did about it -- captured now,
before any real ranking/personalization model exists, so that when one
does, there's a real dataset to evaluate it against instead of starting
blind. See docs/doctrine/CRAVE_MASTER_PRODUCT_INTELLIGENCE_BIBLE.md #16.

Deliberately smaller than that doctrine doc's full spec (no algorithm
version, candidate set, component scores, penalties, or reason codes --
none of those exist yet, since there's no ranking model to log them for).
What's captured is exactly what's real today: which surface showed a
place, at what position, with what percentile standing, and what the
user did about it (impression/click/save/rank). Extend this table when
there's an actual richer signal to attach, not preemptively.
"""
from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin

# Where the place was shown. Kept as a flat string set (not an enum type)
# to match this codebase's existing precedent (ActivityEvent's
# event_type, PlaceImage's moderation_status) -- adding a new surface is
# a one-line change, not a migration.
SURFACE_FEED = "feed"
SURFACE_SEARCH = "search"
SURFACE_MAP = "map"
SURFACE_TRENDING = "trending"
SURFACE_CRAVES = "craves"
VALID_SURFACES = {
    SURFACE_FEED, SURFACE_SEARCH, SURFACE_MAP, SURFACE_TRENDING, SURFACE_CRAVES,
}

# What happened. impression = rendered on screen. click = navigated to
# place detail. save = added to Craves. rank = completed an "I ate here"
# comparison. Deliberately not the full doctrine funnel
# (opened/selected/acted/visited/would_get_again/returns) -- those need
# product surfaces that don't exist yet (no "mark as visited" flow, no
# post-visit rating prompt). Add event types as those surfaces get built,
# not ahead of them.
EVENT_IMPRESSION = "impression"
EVENT_CLICK = "click"
EVENT_SAVE = "save"
EVENT_RANK = "rank"
VALID_EVENT_TYPES = {EVENT_IMPRESSION, EVENT_CLICK, EVENT_SAVE, EVENT_RANK}


class RecommendationEvent(Base, TimestampMixin):
    """
    A single "place X was shown/acted on, on surface Y" event. Append-only
    -- nothing should ever update or delete a row here except a retention
    sweep, once one exists.
    """

    __tablename__ = "recommendation_events"

    __table_args__ = (
        Index("ix_recommendation_events_user_created", "user_id", "created_at"),
        Index("ix_recommendation_events_place_id", "place_id"),
        Index("ix_recommendation_events_surface_type", "surface", "event_type"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # Nullable -- Feed/Search/Map are all browsable signed-out. An
    # anonymous impression is still worth logging (it's still real
    # candidate-set/position data), it just can't be tied to a user.
    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Client-generated, groups anonymous (and signed-in) events from the
    # same app session together without needing an account -- e.g. to
    # later reconstruct "this impression led to this click" even when
    # user_id is null. Not validated/looked-up server-side, purely a
    # grouping key.
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    place_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("places.id", ondelete="SET NULL"), nullable=True
    )

    surface: Mapped[str] = mapped_column(String(16), nullable=False)
    event_type: Mapped[str] = mapped_column(String(16), nullable=False)

    # 0-indexed position within the surface's list at the moment of the
    # event -- e.g. "3rd card in the Feed" or "5th Search result". Null
    # for surfaces without a meaningful linear position (e.g. a Map pin).
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # The percentile-tier value actually shown to the user for this place
    # at event time (see get_rank_percentiles()) -- captured here, not
    # just joined from the place at analysis time, because a place's
    # percentile drifts over time (hourly ranking_update job) and what
    # matters for evaluating "did showing this place work" is what the
    # user actually saw, not its current value.
    rank_percentile: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Only meaningful for surface=search -- the query string that
    # produced this impression/click.
    query: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # City the surface was scoped to at event time (nullable -- a
    # location-based Feed/Map query may have no explicit city selected).
    city_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
