from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
    inspect,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base

if TYPE_CHECKING:
    from app.db.models.place import Place


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PlaceSignal(Base):
    """
    Production-Locked PlaceSignal Model

    DESIGN GUARANTEES:
    - Append-only (no updates after insert)
    - Idempotent (external_event_id dedupe)
    - Normalized value (0–1 enforced)
    - Provider-aware weighting (aggregator layer)
    - Safe for SQLite + Postgres

    ROLE:
    Signals are EVENTS → Aggregator derives STATE (Place scores)
    """

    __tablename__ = "place_signals"

    __table_args__ = (
        Index("ix_place_signals_place_id", "place_id"),
        Index("ix_place_signals_type", "signal_type"),
        Index("ix_place_signals_provider", "provider"),
        Index("ix_place_signals_created_at", "created_at"),
        UniqueConstraint(
            "place_id",
            "provider",
            "signal_type",
            "external_event_id",
            name="uq_place_signal_dedupe",
        ),
    )

    # -----------------------------------------------------
    # IDENTITY
    # -----------------------------------------------------

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    place_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("places.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # -----------------------------------------------------
    # CLASSIFICATION
    # -----------------------------------------------------

    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    signal_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    # signal_class: routing class for this signal
    # Valid values: "discovery" | "enrichment" | "ranking" | "risk"
    # None = unclassified (legacy / pre-routing signals)
    signal_class: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        index=True,
    )

    # -----------------------------------------------------
    # VALUE
    # -----------------------------------------------------

    value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        doc="Normalized value (0–1)",
    )

    raw_value: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    external_event_id: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )

    # -----------------------------------------------------
    # RELATIONSHIP
    # -----------------------------------------------------

    place: Mapped["Place"] = relationship(
        "Place",
        backref="signals",
        passive_deletes=True,
    )

    # -----------------------------------------------------
    # INIT (STRICT NORMALIZATION)
    # -----------------------------------------------------

    def __init__(
        self,
        *,
        place_id: str,
        provider: str,
        signal_type: str,
        value: float,
        raw_value: str | None = None,
        external_event_id: str | None = None,
        signal_class: str | None = None,
    ):
        if not place_id:
            raise ValueError("PlaceSignal requires place_id")

        if not provider:
            raise ValueError("provider cannot be empty")

        if not signal_type:
            raise ValueError("signal_type cannot be empty")

        try:
            normalized_value = max(0.0, min(1.0, float(value)))
        except Exception:
            normalized_value = 0.0

        self.place_id = place_id
        self.provider = provider.strip().lower()
        self.signal_type = signal_type.strip().lower()
        self.value = normalized_value
        self.raw_value = raw_value
        self.external_event_id = external_event_id
        self.signal_class = signal_class

    # -----------------------------------------------------
    # IMMUTABILITY GUARD (APPEND-ONLY)
    # -----------------------------------------------------

    def __setattr__(self, key, value):
        if key in {"place_id", "provider", "signal_type", "external_event_id"}:
            state = inspect(self)
            if state.persistent and getattr(self, key, None) != value:
                raise AttributeError(f"{key} is immutable once set.")
        super().__setattr__(key, value)