from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobRun(Base):
    """
    One row per scheduled-job execution.

    Before this existed, every job in app/scheduler.py logged a single line
    to stdout and nothing else — there was no queryable record of what ran,
    when, whether it succeeded, or what it did. That's a big part of why a
    two-month production outage went unnoticed: even with the app running,
    there was no "did the pipeline actually do anything today" view.

    Written by app.core.job_run_tracker.track_job_run(), which wraps each
    scheduled job body.
    """

    __tablename__ = "job_runs"

    __table_args__ = (
        Index("ix_job_runs_job_name_started", "job_name", "started_at"),
        # Explicit name — index=True on job_name below would route through
        # Base's naming convention and mismatch what's actually deployed
        # (see NAMING_CONVENTION's comment in app/db/models/base.py).
        Index("ix_job_runs_job_name", "job_name"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    job_name: Mapped[str] = mapped_column(String(64), nullable=False)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Short human-readable result, e.g. "promoted=12 processed=50"
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Full traceback on failure, truncated to a sane size.
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
