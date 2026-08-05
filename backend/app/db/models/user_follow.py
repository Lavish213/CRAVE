# app/db/models/user_follow.py
from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin


class UserFollow(Base, TimestampMixin):
    __tablename__ = "user_follows"

    __table_args__ = (
        UniqueConstraint("follower_id", "followee_id", name="uq_user_follows_pair"),
        # `alembic check`/autogenerate always reports this as drift (wanting
        # ck_user_follows_ck_user_follows_no_self_follow — the "ck" naming
        # convention gets applied on top of this explicit name, doubling
        # the prefix). The real deployed constraint is this exact name;
        # renaming it would need a migration for a purely cosmetic change,
        # same known/harmless situation as categories.category_type_enum in
        # app/db/models/category.py.
        CheckConstraint("follower_id != followee_id", name="ck_user_follows_no_self_follow"),
        Index("ix_user_follows_follower", "follower_id"),
        Index("ix_user_follows_followee", "followee_id"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    follower_id: Mapped[str] = mapped_column(String(128), nullable=False)

    followee_id: Mapped[str] = mapped_column(String(128), nullable=False)
