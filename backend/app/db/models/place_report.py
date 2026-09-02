# app/db/models/place_report.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin

REASON_WRONG_HOURS = "wrong_hours"
REASON_CLOSED = "closed"
REASON_DUPLICATE = "duplicate"
REASON_WRONG_MENU = "wrong_menu"
REASON_WRONG_INFO = "wrong_info"
REASON_OTHER = "other"

VALID_REPORT_REASONS = frozenset({
    REASON_WRONG_HOURS,
    REASON_CLOSED,
    REASON_DUPLICATE,
    REASON_WRONG_MENU,
    REASON_WRONG_INFO,
    REASON_OTHER,
})


class PlaceReport(Base, TimestampMixin):
    """
    A user flagging that something about a place itself is wrong --
    hours, closure, a duplicate listing, menu info, or general details.
    The counterpart to ImageReport/VideoReport (see
    app/api/v1/routes/moderation.py) for place-level rather than
    media-level content.

    Deliberately no auto-hide/auto-deactivate path the way ImageReport
    has: taking a whole restaurant off the catalog on report volume
    alone is a much higher-stakes, more reversible-in-the-wrong-
    direction action than hiding one photo. Every report lands in the
    review queue for a human to act on (correct the data, merge a
    duplicate, deactivate a closed place) via existing out-of-band
    tooling -- this only records and queues, it doesn't correct.
    """

    __tablename__ = "place_reports"

    __table_args__ = (
        # One report per person per place -- matches ImageReport's
        # reasoning (a single user shouldn't be able to inflate signal
        # by reporting the same place repeatedly under different reasons).
        UniqueConstraint("place_id", "reporter_id", name="uq_place_reports_place_reporter"),
        Index("ix_place_reports_place", "place_id"),
        Index("ix_place_reports_reporter_id", "reporter_id"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    place_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("places.id", ondelete="CASCADE"),
        nullable=False,
    )

    reporter_id: Mapped[str] = mapped_column(String(128), nullable=False)

    reason: Mapped[str] = mapped_column(String(32), nullable=False)

    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    resolved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
