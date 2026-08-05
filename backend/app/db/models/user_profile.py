# app/db/models/user_profile.py
from __future__ import annotations

from sqlalchemy import Boolean, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin


class UserProfile(Base, TimestampMixin):
    """
    App-specific profile data for a Supabase-authenticated user.

    Supabase owns auth (email/password, session tokens) but has no notion
    of a username/avatar/bio — every other table in this app just stores
    the bare Supabase `sub` claim as a string user_id with nothing to show
    for it. `id` here IS that same string (see app.core.user_auth), not a
    fresh UUID — every other table's user_id already means this row's id.
    """

    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)

    username: Mapped[str] = mapped_column(String(30), nullable=False, unique=True, index=True)

    display_name: Mapped[str | None] = mapped_column(String(60), nullable=True)

    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    bio: Mapped[str | None] = mapped_column(String(280), nullable=True)

    # Governs whether this profile's ranked list (and, later, the profile
    # itself beyond the bare username) is visible to non-followers. True by
    # default — matches every other app in this space (Beli, Letterboxd,
    # Strava): public-by-default with an opt-out, not private-by-default.
    is_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
