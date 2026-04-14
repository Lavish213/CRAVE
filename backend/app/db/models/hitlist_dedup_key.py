# app/db/models/hitlist_dedup_key.py
from __future__ import annotations
import uuid
from sqlalchemy import Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.models.base import Base, TimestampMixin


class HitlistDedupKey(Base, TimestampMixin):
    __tablename__ = "hitlist_dedup_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "dedup_key", name="uq_hitlist_dedup_keys_user_key"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    dedup_key: Mapped[str] = mapped_column(String(128), nullable=False)
