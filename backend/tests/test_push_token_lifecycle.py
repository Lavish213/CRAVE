"""Account-isolation coverage for a device token across sign-out/sign-in."""
from __future__ import annotations

import uuid
from unittest.mock import patch

from app.db.models.device_push_token import DevicePushToken
from app.db.session import SessionLocal
from app.services.notifications.expo_push import send_push_to_user
from app.services.notifications.push_token_service import (
    register_push_token,
    unregister_push_token,
)


def test_token_moves_cleanly_from_signed_out_user_to_next_account():
    db = SessionLocal()
    token = f"ExponentPushToken[{uuid.uuid4().hex}]"

    try:
        register_push_token(
            db,
            user_id="lifecycle-user-a",
            push_token=token,
            platform="ios",
        )
        unregister_push_token(
            db,
            user_id="lifecycle-user-a",
            push_token=token,
        )
        register_push_token(
            db,
            user_id="lifecycle-user-b",
            push_token=token,
            platform="ios",
        )

        rows = (
            db.query(DevicePushToken)
            .filter(DevicePushToken.push_token == token)
            .all()
        )
        assert len(rows) == 1
        assert rows[0].user_id == "lifecycle-user-b"

        with patch(
            "app.services.notifications.expo_push.send_push_to_tokens"
        ) as mock_send:
            send_push_to_user(
                db,
                "lifecycle-user-a",
                title="Old account",
                body="Must not receive this",
            )

        mock_send.assert_called_once_with(
            [],
            title="Old account",
            body="Must not receive this",
            data=None,
        )
    finally:
        db.query(DevicePushToken).filter(
            DevicePushToken.push_token == token
        ).delete()
        db.commit()
        db.close()
