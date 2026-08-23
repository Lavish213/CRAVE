from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin


STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"

VALID_STATUSES = frozenset({STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED})


class MenuSubmission(Base, TimestampMixin):
    """
    A user-submitted menu, staged for moderation before it's ever trusted.

    Deliberately NOT the source of truth for what /places/{id}/menu serves
    — on approval, each item is written as a PlaceClaim (field="menu_item",
    source="user_submission", is_verified_source=True) and run through the
    exact same materialize_menu_truth -> MenuPublisher pipeline every
    scraped source already goes through. That's what lets a submission
    coexist with (and be out-scored by, or corroborate) whatever the
    scrapers already found for the same place, instead of being a second,
    parallel "menu" nobody reconciles.
    """

    __tablename__ = "menu_submissions"

    __table_args__ = (
        Index("ix_menu_submissions_place_status", "place_id", "status"),
        Index("ix_menu_submissions_status_created", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    place_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("places.id", ondelete="CASCADE"),
        nullable=False,
    )

    # JWT-derived user id — always server-set, never client input (see
    # app/api/v1/routes/menu_submissions.py). Same pattern as
    # CraveItem.submitted_by.
    submitted_by: Mapped[str] = mapped_column(String(255), nullable=False)

    # [{"name": str, "category": str | None, "price_cents": int | None,
    #   "description": str | None}, ...] — validated at the API boundary
    # (see MenuItemSubmissionPayload), not re-validated here.
    items: Mapped[list] = mapped_column(JSON, nullable=False)

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=STATUS_PENDING,
        server_default=text(f"'{STATUS_PENDING}'"),
    )

    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
