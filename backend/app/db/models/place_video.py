from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin


# pending    -- upload slot created (R2 presigned URL issued), nothing
#               uploaded yet.
# queued     -- client confirmed the direct-to-storage PUT finished.
#               Picked up by the video-processing scheduler job -- there is
#               deliberately no FastAPI BackgroundTask here (unlike
#               PlaceImage's per-upload flow): ffmpeg compression + the food
#               classifier are real CPU work, and the whole reason the
#               scheduler runs as its own Railway service (see
#               app/scheduler_worker.py) is to keep exactly this kind of
#               work off the process serving live requests.
# processing -- the worker has claimed this row and is actively working it.
# approved   -- passed every gate, live in the feed.
# rejected   -- failed a real content gate (duration/food_score/corrupt/
#               too_large/abandoned_upload) -- a normal, expected outcome,
#               not a bug.
# failed     -- the pipeline itself errored (storage/ffmpeg/classifier
#               exception) -- something to look at, not a content judgment.
STATUS_PENDING = "pending"
STATUS_QUEUED = "queued"
STATUS_PROCESSING = "processing"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_FAILED = "failed"

VALID_STATUSES = frozenset({
    STATUS_PENDING, STATUS_QUEUED, STATUS_PROCESSING,
    STATUS_APPROVED, STATUS_REJECTED, STATUS_FAILED,
})

# Reasons a video can land in 'rejected'. 'processing_error' is 'failed'
# territory instead -- see the status comment above.
REJECT_DURATION = "duration"
REJECT_FOOD_SCORE = "food_score"
REJECT_CORRUPT = "corrupt"
REJECT_TOO_LARGE = "too_large"
REJECT_ABANDONED_UPLOAD = "abandoned_upload"


class PlaceVideo(Base, TimestampMixin):
    """
    A user-recorded short food video attached to a place, staged through
    upload -> compress -> food-score -> feed, mirroring PlaceImage's
    upload pipeline shape (app/services/upload/) but as its own table --
    duration/food_score/template_id and the extra 'queued' status have no
    equivalent on PlaceImage, and giving video its own lifecycle keeps
    that already-well-tested photo path untouched.
    """

    __tablename__ = "place_videos"

    __table_args__ = (
        Index("ix_place_videos_place_status", "place_id", "status"),
        # Supports the feed query (status='approved', newest first) and
        # the worker's batch pickup (status IN ('queued', ...), oldest
        # first) -- see video_processing_worker.py.
        Index("ix_place_videos_status_created", "status", "created_at"),
        Index("ix_place_videos_uploaded_by", "uploaded_by"),
        # An offline-recorded clip retries /videos/request with the same
        # client_id after a crash/lost-response mid-sync (see
        # video_upload_service.py) -- unique (not just an index) so two
        # concurrent retries for the same clip can't both insert a row;
        # the second fails the constraint and the service falls back to
        # the row the first insert already created. NULL-safe: most videos
        # (recorded with a live connection) never set client_id at all,
        # and a partial unique index ignores NULLs entirely.
        Index(
            "uq_place_videos_client_id", "client_id",
            unique=True,
            postgresql_where=text("client_id IS NOT NULL"),
            sqlite_where=text("client_id IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    place_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("places.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Supabase user id of the recorder. Unlike PlaceImage.uploaded_by,
    # never null -- there is no scraped/legacy source for video.
    uploaded_by: Mapped[str] = mapped_column(String(128), nullable=False)

    template_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("video_templates.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Client-generated id from the offline record flow (see
    # frontend/src/stores/videoQueueStore.ts) -- lets a retried
    # /videos/request after a crash/lost-response find (and reuse) the row
    # it already created instead of creating a duplicate. Null for any
    # video recorded with a live connection, which never needs this.
    client_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    orig_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    processed_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    thumb_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    food_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=STATUS_PENDING,
        server_default=text(f"'{STATUS_PENDING}'"),
    )

    reject_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)

    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
