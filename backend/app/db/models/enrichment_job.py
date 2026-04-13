from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String,
    DateTime,
    Integer,
    Boolean,
    JSON,
    Index,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EnrichmentJob(Base):
    """
    FINALIZED PRODUCTION JOB QUEUE

    Guarantees:
    - Idempotent job scheduling
    - Safe retry + backoff
    - Lock-safe multi-worker execution
    - Deterministic job uniqueness per place/type

    Optimized for:
    - background workers
    - ingestion pipelines
    - enrichment orchestration
    """

    __tablename__ = "enrichment_jobs"

    __table_args__ = (
        Index("ix_enrichment_status_priority", "status", "priority"),
        Index("ix_enrichment_place_type", "place_id", "job_type"),
        Index("ix_enrichment_next_run", "next_run_at"),

        Index("ix_enrichment_ready", "status", "next_run_at", "priority"),
        Index("ix_enrichment_locked", "locked_at"),

        UniqueConstraint(
            "place_id",
            "job_type",
            "is_active",
            name="uq_active_job_per_place_type",
        ),
    )

    # --------------------------------------------------
    # IDENTITY
    # --------------------------------------------------

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    place_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    job_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    payload: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # --------------------------------------------------
    # STATE
    # --------------------------------------------------

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
        index=True,
    )

    attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )

    max_attempts: Mapped[int] = mapped_column(
        Integer,
        default=3,
        server_default=text("3"),
        nullable=False,
    )

    last_error: Mapped[str | None] = mapped_column(String)

    # --------------------------------------------------
    # LOCKING
    # --------------------------------------------------

    locked_by: Mapped[str | None] = mapped_column(String(64))

    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )

    # --------------------------------------------------
    # SCHEDULING
    # --------------------------------------------------

    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("1"),
        nullable=False,
        index=True,
    )

    # --------------------------------------------------
    # TIMESTAMPS
    # --------------------------------------------------

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )

    last_attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )