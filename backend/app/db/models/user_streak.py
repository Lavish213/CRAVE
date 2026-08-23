# app/db/models/user_streak.py
from __future__ import annotations

from datetime import date as date_type

from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin


class UserStreak(Base, TimestampMixin):
    """
    One row per user -- the Duolingo-style daily streak counter (Beli's
    gamification hook). See app.services.social.streak_service for the
    actual day-boundary logic; this is just the stored state.

    last_active_date is a calendar date, not a timestamp -- it's always
    computed server-side from the current UTC instant converted into the
    user's own IANA timezone (client-supplied, validated), never trusted
    directly from the device clock. See streak_service's module
    docstring for why that distinction matters.
    """

    __tablename__ = "user_streaks"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)

    current_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    longest_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    last_active_date: Mapped[date_type | None] = mapped_column(Date, nullable=True)
