# app/db/models/hitlist_save.py
from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.models.base import Base, TimestampMixin


class HitlistSave(Base, TimestampMixin):
    __tablename__ = "hitlist_saves"
    __table_args__ = (
        UniqueConstraint("user_id", "dedup_key", name="uq_hitlist_saves_user_dedup"),
        Index("ix_hitlist_saves_user_created", "user_id", "created_at"),
        Index("ix_hitlist_saves_place_id", "place_id"),
        Index("ix_hitlist_saves_status", "resolution_status"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    place_name: Mapped[str] = mapped_column(String(256), nullable=False)
    source_platform: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    place_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("places.id", ondelete="SET NULL"), nullable=True
    )
    resolution_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="raw", index=True
    )
    dedup_key: Mapped[str] = mapped_column(String(128), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --------------------------------------------------
    # MEMORY (E2) -- whether/when the user actually visited a saved
    # place, plus a free-text note. Only meaningful for app-created
    # saves (dedup_key starting "save:") -- craves-discovery rows never
    # surface these. `visited_at` is cleared alongside `visited=False`,
    # not left stale, so it never reports a visit that got un-marked.
    # See docs/E2_E3_E10_PRODUCT_TRADEOFFS_2026-08-31.md.
    # --------------------------------------------------
    visited: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    visited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
