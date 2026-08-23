# app/db/models/user_block.py
from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin


class UserBlock(Base, TimestampMixin):
    """
    One-directional: blocker_id has blocked blocked_id. Enforcement (hiding
    the blocked user's content from the blocker, preventing new follows in
    either direction) lives in the read paths that already filter by
    user_id — see app.services.social.block_service for the exact set.
    """

    __tablename__ = "user_blocks"

    __table_args__ = (
        UniqueConstraint("blocker_id", "blocked_id", name="uq_user_blocks_pair"),
        CheckConstraint("blocker_id != blocked_id", name="ck_user_blocks_no_self_block"),
        Index("ix_user_blocks_blocker", "blocker_id"),
        Index("ix_user_blocks_blocked", "blocked_id"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    blocker_id: Mapped[str] = mapped_column(String(128), nullable=False)

    blocked_id: Mapped[str] = mapped_column(String(128), nullable=False)
