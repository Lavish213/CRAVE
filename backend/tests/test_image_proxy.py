"""
Coverage for the /api/v1/image Google Places photo proxy.

Context: place photos never loaded in the app — cards sat on their
blurhash placeholder indefinitely. A contributing cause was this route
requesting a fixed 1600px-wide source image for EVERY caller including
small feed thumbnails, then buffering the whole thing in memory before
sending a single byte. A feed full of cards meant many concurrent
multi-hundred-KB fetches, which the client gave up on.

These tests pin the fix: a thumbnail-sized default, an opt-up width
param that's clamped, streamed (not buffered) relay, and hard caching.
The SSRF guard on `ref` is covered here too since this route takes a
client-supplied path that gets interpolated into an upstream URL.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient

import app.api.v1.routes.image as image_route
from app.main import app

client = TestClient(app)

_VALID_REF = "places/ChIJabc123/photos/AaBbCc-_123"


def _fake_upstream(chunks=(b"aaa", b"bbb"), status=200, content_type="image/jpeg"):
    fake = MagicMock()
    fake.status_code = status
    fake.headers = {"Content-Type": content_type}
    fake.iter_content = lambda chunk_size: list(chunks)
    fake.close = MagicMock()
    return fake


@pytest.fixture(autouse=True)
def _configured_api_key():
    with patch.object(image_route.settings, "google_places_api_key", "fake-key"):
        yield


def test_defaults_to_thumbnail_width_not_full_size():
    fake = _fake_upstream()
    with patch.object(image_route.requests, "get", return_value=fake) as mock_get:
        resp = client.get(f"/api/v1/image?ref={_VALID_REF}")

    assert resp.status_code == 200
    assert f"maxWidthPx={image_route._DEFAULT_WIDTH}" in mock_get.call_args[0][0]
    # Guard the intent, not just the current number: the default must stay
    # meaningfully smaller than the max, or the original bug is back.
    assert image_route._DEFAULT_WIDTH < image_route._MAX_WIDTH


def test_explicit_width_is_honored():
    fake = _fake_upstream()
    with patch.object(image_route.requests, "get", return_value=fake) as mock_get:
        client.get(f"/api/v1/image?ref={_VALID_REF}&w=1600")

    assert "maxWidthPx=1600" in mock_get.call_args[0][0]


def test_width_is_clamped_at_both_ends():
    fake = _fake_upstream()

    with patch.object(image_route.requests, "get", return_value=fake) as mock_get:
        client.get(f"/api/v1/image?ref={_VALID_REF}&w=99999")
    assert f"maxWidthPx={image_route._MAX_WIDTH}" in mock_get.call_args[0][0]

    with patch.object(image_route.requests, "get", return_value=fake) as mock_get:
        client.get(f"/api/v1/image?ref={_VALID_REF}&w=1")
    assert f"maxWidthPx={image_route._MIN_WIDTH}" in mock_get.call_args[0][0]


def test_relays_all_chunks_in_order():
    fake = _fake_upstream(chunks=(b"one", b"two", b"three"))
    with patch.object(image_route.requests, "get", return_value=fake):
        resp = client.get(f"/api/v1/image?ref={_VALID_REF}")

    assert resp.content == b"onetwothree"


def test_closes_upstream_response_after_streaming():
    # The relay generator owns the upstream connection — if it doesn't
    # close it, a busy feed leaks sockets on the server.
    fake = _fake_upstream()
    with patch.object(image_route.requests, "get", return_value=fake):
        client.get(f"/api/v1/image?ref={_VALID_REF}")

    fake.close.assert_called()


def test_sets_long_immutable_cache_header():
    fake = _fake_upstream()
    with patch.object(image_route.requests, "get", return_value=fake):
        resp = client.get(f"/api/v1/image?ref={_VALID_REF}")

    cache_control = resp.headers.get("cache-control", "")
    assert "immutable" in cache_control
    assert "max-age=" in cache_control


@pytest.mark.parametrize("bad_ref", [
    "https://evil.example.com/steal",
    "../../etc/passwd",
    "places/abc/photos/xyz/../../..",
    "notplaces/abc/photos/xyz",
    "places/abc",
])
def test_rejects_refs_that_do_not_match_the_google_photo_pattern(bad_ref):
    resp = client.get("/api/v1/image", params={"ref": bad_ref})
    assert resp.status_code == 400


def test_upstream_failure_returns_404_and_closes_connection():
    fake = _fake_upstream(status=403)
    with patch.object(image_route.requests, "get", return_value=fake):
        resp = client.get(f"/api/v1/image?ref={_VALID_REF}")

    assert resp.status_code == 404
    fake.close.assert_called()


def test_upstream_exception_returns_502():
    with patch.object(image_route.requests, "get", side_effect=RuntimeError("boom")):
        resp = client.get(f"/api/v1/image?ref={_VALID_REF}")

    assert resp.status_code == 502


def test_returns_503_when_api_key_is_unconfigured():
    with patch.object(image_route.settings, "google_places_api_key", ""):
        resp = client.get(f"/api/v1/image?ref={_VALID_REF}")

    assert resp.status_code == 503
