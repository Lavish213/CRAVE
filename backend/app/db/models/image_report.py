# app/db/models/image_report.py
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin

REASON_INAPPROPRIATE = "inappropriate"
REASON_NOT_THIS_PLACE = "not_this_place"
REASON_LOW_QUALITY = "low_quality"
REASON_SPAM = "spam"
REASON_OTHER = "other"

VALID_REPORT_REASONS = frozenset({
    REASON_INAPPROPRIATE,
    REASON_NOT_THIS_PLACE,
    REASON_LOW_QUALITY,
    REASON_SPAM,
    REASON_OTHER,
})

# Distinct reporters needed before a live photo is pulled automatically.
# One report is an opinion and can be malicious (a rival business, a
# grudge); several independent people converging is a signal. Anything
# pulled this way lands in the review queue rather than being deleted, so
# a bad-faith pile-on is recoverable.
AUTO_HIDE_REPORT_COUNT = 3


class ImageReport(Base, TimestampMixin):
    """
    A user flagging a photo. Reactive moderation — the counterpart to the
    automated screening in app/services/images/upload_moderation.py, and
    the only path that catches what automation misses (a real, sharp,
    safe-looking photo that is simply of the wrong restaurant).
    """

    __tablename__ = "image_reports"

    __table_args__ = (
        # One report per person per image — otherwise a single user could
        # trip the auto-hide threshold alone.
        UniqueConstraint("image_id", "reporter_id", name="uq_image_reports_image_reporter"),
        Index("ix_image_reports_image", "image_id"),
        # Explicit name — index=True on reporter_id below would route
        # through Base's naming convention and mismatch what's actually
        # deployed (see NAMING_CONVENTION's comment in app/db/models/base.py).
        Index("ix_image_reports_reporter_id", "reporter_id"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    image_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("place_images.id", ondelete="CASCADE"),
        nullable=False,
    )

    reporter_id: Mapped[str] = mapped_column(String(128), nullable=False)

    reason: Mapped[str] = mapped_column(String(32), nullable=False)

    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
