"""
Coverage for the SSRF protection added to app.workers.share_parser_worker.

POST /api/v1/share accepts arbitrary "web"/"other" URLs by design (sharing
a blog post about a restaurant is a real use case), so this can't be a
domain allowlist — before this fix, any authenticated user could get the
worker to issue an outbound GET to any URL they supplied, including cloud
metadata endpoints (169.254.169.254) or internal-network addresses, via
POST /api/v1/share. httpx's follow_redirects=True also meant a URL that
looked safe on first fetch could 30x into an internal address.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.workers.share_parser_worker import (
    _is_public_ip,
    _is_safe_url,
    _safe_get,
)


@pytest.mark.parametrize(
    "ip,expected",
    [
        ("169.254.169.254", False),  # cloud metadata endpoint
        ("127.0.0.1", False),        # loopback
        ("10.0.0.5", False),         # RFC1918 private
        ("172.16.0.1", False),       # RFC1918 private
        ("192.168.1.1", False),      # RFC1918 private
        ("0.0.0.0", False),          # unspecified
        ("224.0.0.1", False),        # multicast
        ("8.8.8.8", True),           # public
        ("1.1.1.1", True),           # public
        ("not-an-ip", False),        # invalid input fails closed
    ],
)
def test_is_public_ip(ip, expected):
    assert _is_public_ip(ip) is expected


def test_is_safe_url_blocks_ip_literal_loopback():
    assert _is_safe_url("http://127.0.0.1/steal-secrets") is False


def test_is_safe_url_blocks_cloud_metadata_ip_literal():
    assert _is_safe_url("http://169.254.169.254/latest/meta-data/") is False


def test_is_safe_url_allows_public_ip_literal():
    assert _is_safe_url("http://8.8.8.8/") is True


def test_is_safe_url_rejects_non_http_scheme():
    assert _is_safe_url("ftp://8.8.8.8/") is False
    assert _is_safe_url("file:///etc/passwd") is False


def test_is_safe_url_rejects_malformed_url():
    assert _is_safe_url("not a url at all") is False


def test_is_safe_url_rejects_unresolvable_host():
    assert _is_safe_url("http://this-host-should-never-resolve.invalid/") is False


def test_safe_get_raises_immediately_for_unsafe_initial_url():
    with pytest.raises(ValueError, match="unsafe URL blocked"):
        _safe_get("http://127.0.0.1/", headers={}, timeout=1.0)


def test_safe_get_blocks_a_redirect_into_an_internal_address():
    # Simulates the exact bypass follow_redirects=True was vulnerable to:
    # a public-looking URL that 30x's to an internal one.
    redirect_response = MagicMock()
    redirect_response.is_redirect = True
    redirect_response.headers = {"location": "http://127.0.0.1/internal-only"}

    with patch("app.workers.share_parser_worker.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.get.return_value = redirect_response
        mock_client_cls.return_value.__enter__.return_value = mock_client

        with pytest.raises(ValueError, match="unsafe URL blocked"):
            _safe_get("http://8.8.8.8/looks-fine", headers={}, timeout=1.0)
