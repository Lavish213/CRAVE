"""
Coverage for app.services.upload.r2_client.generate_public_url — the fix
for a confirmed, real bug: it used to build public URLs off the R2 S3 API
endpoint (`{bucket}.{account}.r2.cloudflarestorage.com`), which always
requires SigV4-signed requests no matter what a bucket's public-access
setting is. Every URL written to the database by that old implementation
was unreachable from the app — confirmed in production by the R2 bucket
sitting at 0 objects / 0 operations despite the upload code paths having
run. generate_public_url now requires R2_PUBLIC_BASE_URL (the bucket's
actual Public Development URL or a mapped custom domain) and raises
rather than silently building another unreachable URL.

R2_PUBLIC_BASE_URL is a module-level constant computed from the
environment at import time, so tests that vary it have to reload the
module after monkeypatching — see the `reload_r2_client` fixture.
"""
from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

import pytest

from app.services.upload import r2_client as r2_client_module


@pytest.fixture
def reload_r2_client(monkeypatch):
    def _reload():
        importlib.reload(r2_client_module)
        return r2_client_module

    yield _reload

    # monkeypatch's own teardown restores the real env after this fixture
    # tears down, but that happens too late for anything reloaded *during*
    # this test to pick it back up — reload once more now, before that,
    # so the module's cached constants match the restored env for
    # whatever test runs next.
    monkeypatch.undo()
    importlib.reload(r2_client_module)


def test_generate_public_url_raises_when_unconfigured(monkeypatch, reload_r2_client):
    monkeypatch.setenv("R2_PUBLIC_BASE_URL", "")
    mod = reload_r2_client()

    with pytest.raises(RuntimeError):
        mod.generate_public_url("google-photos/some-place/abc123.jpg")


def test_generate_public_url_builds_from_the_public_base_url(monkeypatch, reload_r2_client):
    monkeypatch.setenv("R2_PUBLIC_BASE_URL", "https://pub-abc123.r2.dev")
    mod = reload_r2_client()

    assert (
        mod.generate_public_url("google-photos/some-place/abc123.jpg")
        == "https://pub-abc123.r2.dev/google-photos/some-place/abc123.jpg"
    )


def test_generate_public_url_strips_a_trailing_slash_from_the_base(monkeypatch, reload_r2_client):
    monkeypatch.setenv("R2_PUBLIC_BASE_URL", "https://pub-abc123.r2.dev/")
    mod = reload_r2_client()

    assert mod.generate_public_url("key.jpg") == "https://pub-abc123.r2.dev/key.jpg"


def test_generate_public_url_never_uses_the_private_s3_api_host(monkeypatch, reload_r2_client):
    """Regression guard for the actual bug: the old implementation's URL
    always pointed at the S3 API endpoint, not a publicly loadable one."""
    monkeypatch.setenv("R2_PUBLIC_BASE_URL", "https://pub-abc123.r2.dev")
    monkeypatch.setenv("R2_ACCOUNT_ID", "some-account-id")
    monkeypatch.setenv("R2_BUCKET", "crave")
    mod = reload_r2_client()

    url = mod.generate_public_url("key.jpg")

    assert "r2.cloudflarestorage.com" not in url


def test_download_to_file_uses_signed_http_stream_not_botocore_body(tmp_path):
    """Regression guard for the Railway worker's StreamingBody recursion.

    Keep botocore responsible only for signing.  The actual response body is
    streamed by requests, so a deployed botocore response-wrapper regression
    cannot strand every queued video before ffmpeg starts.
    """
    client = MagicMock()
    client.generate_presigned_url.return_value = "https://signed.example/video"
    response = MagicMock()
    response.__enter__.return_value = response
    response.iter_content.return_value = [b"first", b"", b"second"]
    destination = tmp_path / "video.mp4"

    with patch.object(r2_client_module, "_get_s3_client", return_value=client), patch.object(
        r2_client_module.requests, "get", return_value=response
    ) as get:
        r2_client_module.download_to_file("places/p/videos/orig/v.mp4", str(destination))

    client.generate_presigned_url.assert_called_once_with(
        ClientMethod="get_object",
        Params={"Bucket": r2_client_module.R2_BUCKET, "Key": "places/p/videos/orig/v.mp4"},
        ExpiresIn=300,
    )
    get.assert_called_once_with(
        "https://signed.example/video", stream=True, timeout=(10, 120)
    )
    response.raise_for_status.assert_called_once_with()
    assert destination.read_bytes() == b"firstsecond"
