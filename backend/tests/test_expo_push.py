"""
Coverage for app.services.notifications.expo_push. Every function here
is best-effort by contract -- nothing it does should ever raise, matching
how video_processing_worker.py calls it from inside an approve/reject
path that must still commit the video's own outcome regardless of
whether the notification succeeds.
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
import requests

from app.db.session import SessionLocal
from app.db.models.device_push_token import DevicePushToken
from app.services.notifications.expo_push import send_push_to_tokens, send_push_to_user


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_no_tokens_skips_the_http_call():
    with patch("app.services.notifications.expo_push.requests.post") as mock_post:
        send_push_to_tokens([], title="t", body="b")

    mock_post.assert_not_called()


def test_sends_one_request_for_a_small_batch():
    fake_resp = MagicMock()
    fake_resp.json.return_value = {"data": [{"status": "ok"}]}
    with patch("app.services.notifications.expo_push.requests.post", return_value=fake_resp) as mock_post:
        send_push_to_tokens(["tok-1"], title="Hi", body="World", data={"k": "v"})

    mock_post.assert_called_once()
    _args, kwargs = mock_post.call_args
    sent_messages = kwargs["json"]
    assert sent_messages == [{"to": "tok-1", "title": "Hi", "body": "World", "data": {"k": "v"}}]


def test_batches_over_the_expo_cap():
    tokens = [f"tok-{i}" for i in range(150)]
    fake_resp = MagicMock()
    fake_resp.json.return_value = {"data": [{"status": "ok"}] * 100}
    with patch("app.services.notifications.expo_push.requests.post", return_value=fake_resp) as mock_post:
        send_push_to_tokens(tokens, title="t", body="b")

    assert mock_post.call_count == 2  # 100 + 50


def test_network_failure_is_swallowed_not_raised():
    with patch("app.services.notifications.expo_push.requests.post",
               side_effect=requests.ConnectionError("boom")):
        send_push_to_tokens(["tok-1"], title="t", body="b")  # must not raise


def test_a_per_token_delivery_error_is_logged_not_raised():
    fake_resp = MagicMock()
    fake_resp.json.return_value = {
        "data": [{"status": "error", "message": "DeviceNotRegistered"}]
    }
    with patch("app.services.notifications.expo_push.requests.post", return_value=fake_resp):
        send_push_to_tokens(["tok-1"], title="t", body="b")  # must not raise


def test_send_to_user_looks_up_every_registered_device(db):
    suffix = uuid.uuid4().hex[:8]
    user_id = f"push-user-{suffix}"
    t1, t2 = DevicePushToken(push_token=f"tok-a-{suffix}", user_id=user_id, platform="ios"), \
        DevicePushToken(push_token=f"tok-b-{suffix}", user_id=user_id, platform="android")
    db.add_all([t1, t2])
    db.commit()

    try:
        with patch("app.services.notifications.expo_push.send_push_to_tokens") as mock_send:
            send_push_to_user(db, user_id, title="t", body="b")

        mock_send.assert_called_once()
        sent_tokens = set(mock_send.call_args[0][0])
        assert sent_tokens == {t1.push_token, t2.push_token}
    finally:
        db.query(DevicePushToken).filter(DevicePushToken.user_id == user_id).delete()
        db.commit()


def test_send_to_user_with_no_devices_sends_nothing(db):
    with patch("app.services.notifications.expo_push.send_push_to_tokens") as mock_send:
        send_push_to_user(db, "user-with-no-devices", title="t", body="b")

    mock_send.assert_called_once_with([], title="t", body="b", data=None)
