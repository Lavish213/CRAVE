from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import MetaData, DateTime, JSON
from sqlalchemy.dialects.postgresql import JSONB


# ---------------------------------------------------------
# NAMING CONVENTION (ALEMBIC SAFE)
# ---------------------------------------------------------

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


# ---------------------------------------------------------
# GLOBAL METADATA
# ---------------------------------------------------------

metadata = MetaData(
    naming_convention=NAMING_CONVENTION
)


# ---------------------------------------------------------
# GLOBAL BASE
# ---------------------------------------------------------

class Base(DeclarativeBase):
    __abstract__ = True
    metadata = metadata


# ---------------------------------------------------------
# SHARED HELPERS
# ---------------------------------------------------------

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------
# SHARED TYPES
# ---------------------------------------------------------

JSONType = JSON().with_variant(JSONB, "postgresql")


# ---------------------------------------------------------
# MIXINS
# ---------------------------------------------------------

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )


__all__ = [
    "Base",
    "metadata",
    "utcnow",
    "JSONType",
    "TimestampMixin",
]