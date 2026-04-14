# app/db/models/hitlist_suggestion.py
from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.models.base import Base, TimestampMixin


class HitlistSuggestion(Base, TimestampMixin):
    __tablename__ = "hitlist_suggestions"
    __table_args__ = (
        Index("ix_hitlist_suggestions_user_created", "user_id", "created_at"),
        Index("ix_hitlist_suggestions_name_city", "place_name", "city_hint"),
        Index("ix_hitlist_suggestions_resolved_place", "resolved_place_id"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    place_name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    city_hint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_platform: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    resolved_place_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("places.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
