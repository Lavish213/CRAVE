from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import MetaData, DateTime, JSON
from sqlalchemy.dialects.postgresql import JSONB


# ---------------------------------------------------------
# NAMING CONVENTION (ALEMBIC SAFE)
# ---------------------------------------------------------

NAMING_CONVENTION = {
    # column_0_label (not column_0_name) resolves to "<tablename>_<colname>",
    # which the "ix" template below then prefixes with %(table_name)s AGAIN —
    # doubling it (e.g. ix_categories_categories_type). That looks like a
    # bug, and briefly got "fixed" to column_0_name during a full-app audit
    # — but don't do that: a scan of every migration found 85+ existing
    # indexes across most of the original schema (categories, places,
    # menu_items, discovery_candidates, etc.) genuinely deployed with this
    # doubled name; it's the long-standing real convention, not an error.
    # Switching to column_0_name flips `alembic check` false-positive drift
    # from the handful of newer tables (activity_events, place_rankings,
    # user_follows — see their models for the real fix) onto the entire
    # rest of the schema instead. Net worse. Leave this as-is.
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