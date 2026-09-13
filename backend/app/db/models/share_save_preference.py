"""A user's explicit preference for a place imported through a CRAVE share."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ShareSavePreference(Base):
    """Prevent a repaired share worker from undoing an explicit unsave.

    The row is intentionally scoped to ``(user_id, place_id)`` rather than a
    single CraveItem: several links can resolve to one place, but one explicit
    "remove from Saves" decision must apply to all of them.
    """

    __tablename__ = "share_save_preferences"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    place_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("places.id", ondelete="CASCADE"), primary_key=True
    )
    opted_out_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
