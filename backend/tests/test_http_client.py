"""
Regression test for app/services/network/http_client.py — found live in
production logs: _create_client() unconditionally passes http2=True to
httpx.Client, which requires the optional `h2` package. `h2` was never in
requirements.txt, so every single call raised ImportError
("Using http2=True, but the 'h2' package is not installed") — every
outbound fetch through get_http_client() (menu extraction, website
scraping) was failing, logged but never surfaced as anything actionable.
Fixed by adding h2 to requirements.txt; this test guards against it being
dropped again in the future.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.network.http_client import _create_client


def test_create_client_with_http2_does_not_raise():
    client = _create_client()
    try:
        assert client is not None
    finally:
        client.close()
