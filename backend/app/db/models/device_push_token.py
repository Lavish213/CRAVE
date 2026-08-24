# app/db/models/device_push_token.py
from __future__ import annotations

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin

PLATFORM_IOS = "ios"
PLATFORM_ANDROID = "android"

VALID_PLATFORMS = frozenset({PLATFORM_IOS, PLATFORM_ANDROID})


class DevicePushToken(Base, TimestampMixin):
    """
    An Expo push token for one device install (see
    app/services/notifications/expo_push.py). Keyed by the token itself,
    not (user_id, token) -- a token identifies a device install, not a
    user. Registering the same token again just moves this row to
    whichever user_id is signed in now, so a device that logs out and
    into a different account doesn't keep a stale row still pointing
    notifications at the account it's no longer signed into.
    """

    __tablename__ = "device_push_tokens"

    __table_args__ = (
        Index("ix_device_push_tokens_user_id", "user_id"),
    )

    push_token: Mapped[str] = mapped_column(String(255), primary_key=True)

    user_id: Mapped[str] = mapped_column(String(128), nullable=False)

    platform: Mapped[str] = mapped_column(String(16), nullable=False)
