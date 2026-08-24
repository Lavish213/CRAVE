# app/db/models/video_report.py
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin

# Same reason vocabulary as ImageReport (app/db/models/image_report.py),
# duplicated rather than imported -- PlaceVideo already keeps its own
# lifecycle independent of PlaceImage's (see place_video.py's class
# docstring), and this follows the same precedent rather than coupling
# the two moderation systems together.
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

# Distinct reporters needed before a live video is pulled automatically.
# One report is an opinion and can be malicious; several independent
# people converging is a signal. Anything pulled this way lands in the
# review queue rather than being deleted, so a bad-faith pile-on is
# recoverable. Same threshold and reasoning as ImageReport.
AUTO_HIDE_REPORT_COUNT = 3


class VideoReport(Base, TimestampMixin):
    """
    A user flagging a food video. Reactive moderation -- there is no
    automated content screening for video the way upload_moderation.py
    screens photos (see PlaceVideo's food_score gate, which judges "is
    this food" not "is this appropriate"), so reports are the only
    takedown path for video content that passes the pipeline but
    shouldn't be shown.
    """

    __tablename__ = "video_reports"

    __table_args__ = (
        # One report per person per video -- otherwise a single user could
        # trip the auto-hide threshold alone.
        UniqueConstraint("video_id", "reporter_id", name="uq_video_reports_video_reporter"),
        Index("ix_video_reports_video", "video_id"),
        Index("ix_video_reports_reporter_id", "reporter_id"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    video_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("place_videos.id", ondelete="CASCADE"),
        nullable=False,
    )

    reporter_id: Mapped[str] = mapped_column(String(128), nullable=False)

    reason: Mapped[str] = mapped_column(String(32), nullable=False)

    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
