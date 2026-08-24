# app/services/notifications/push_token_service.py
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.device_push_token import DevicePushToken, VALID_PLATFORMS


def register_push_token(
    db: Session, *, user_id: str, push_token: str, platform: str
) -> DevicePushToken:
    """
    Upserts by push_token (the primary key -- see DevicePushToken's
    docstring for why it's keyed on the token, not (user_id, token)). A
    device re-registering under a different signed-in account moves the
    existing row to that account rather than leaving a second, stale one
    behind for the old account.
    """
    if platform not in VALID_PLATFORMS:
        raise ValueError(f"invalid platform: {platform!r}")

    row = (
        db.query(DevicePushToken)
        .filter(DevicePushToken.push_token == push_token)
        .one_or_none()
    )
    if row is None:
        row = DevicePushToken(push_token=push_token, user_id=user_id, platform=platform)
        db.add(row)
    else:
        row.user_id = user_id
        row.platform = platform
    db.commit()
    return row


def unregister_push_token(db: Session, *, user_id: str, push_token: str) -> None:
    """
    Scoped to user_id so a caller can only remove their own device's
    registration, not one guessed/leaked belonging to someone else.
    Deliberately a no-op (not a 404) if the token isn't theirs or doesn't
    exist -- the caller's own device state is the same either way.
    """
    db.query(DevicePushToken).filter(
        DevicePushToken.push_token == push_token,
        DevicePushToken.user_id == user_id,
    ).delete()
    db.commit()
