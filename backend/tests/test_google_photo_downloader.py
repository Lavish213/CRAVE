"""
Coverage for app.services.images.google_photo_downloader — the byte-level
fetch StaleImageRefresher uses to pull a fresh Google Places (New) photo
down so it can be stored durably in R2, instead of the app depending on
Google's (not-permanent) photo resource name forever.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.services.images.google_photo_downloader as downloader

_VALID_REF = "places/ChIJabc123/photos/AaBbCc-_123"


def _fake_response(status=200, content=b"binarydata", content_type="image/jpeg"):
    fake = MagicMock()
    fake.status_code = status
    fake.headers = {"Content-Type": content_type}
    fake.content = content
    return fake


def test_returns_none_for_invalid_ref():
    with patch.object(downloader.settings, "google_places_api_key", "fake-key"):
        assert downloader.fetch_photo_bytes("../../etc/passwd") is None


def test_returns_none_when_api_key_unconfigured():
    with patch.object(downloader.settings, "google_places_api_key", ""):
        assert downloader.fetch_photo_bytes(_VALID_REF) is None


def test_returns_bytes_and_content_type_on_success():
    fake = _fake_response(content=b"jpegbytes", content_type="image/jpeg")
    with patch.object(downloader.settings, "google_places_api_key", "fake-key"), \
         patch.object(downloader.requests, "get", return_value=fake) as mock_get:
        result = downloader.fetch_photo_bytes(_VALID_REF)

    assert result == (b"jpegbytes", "image/jpeg")
    assert f"maxWidthPx={downloader._DEFAULT_WIDTH}" in mock_get.call_args[0][0]


def test_returns_none_on_upstream_error_status():
    fake = _fake_response(status=404)
    with patch.object(downloader.settings, "google_places_api_key", "fake-key"), \
         patch.object(downloader.requests, "get", return_value=fake):
        assert downloader.fetch_photo_bytes(_VALID_REF) is None


def test_returns_none_on_request_exception():
    with patch.object(downloader.settings, "google_places_api_key", "fake-key"), \
         patch.object(downloader.requests, "get", side_effect=RuntimeError("boom")):
        assert downloader.fetch_photo_bytes(_VALID_REF) is None
