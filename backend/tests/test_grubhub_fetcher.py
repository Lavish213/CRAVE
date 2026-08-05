"""
Coverage for the Grubhub cookie-expiry signal added after a production audit
found that an expired/missing GRUBHUB_COOKIES session silently returned None
from fetch_grubhub_menu() — identical to "this place just has no menu" to
every caller (menu_orchestrator, menu_worker). A 401 or a missing env var now
raises GrubhubCookiesExpired internally, which fetch_grubhub_menu() catches
and logs as a distinct, greppable event (grubhub_cookies_expired) instead of
the generic grubhub_fetch_failed warning every other failure produces —
while still returning None to preserve the existing Optional[Dict] contract
for callers.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.menu.fetchers.grubhub_fetcher import (
    GrubhubCookiesExpired,
    _default_fetcher,
    fetch_grubhub_menu,
)


def _place(**overrides):
    base = {"id": "place-1", "grubhub_url": "https://www.grubhub.com/restaurant/some-place/12345"}
    base.update(overrides)
    return SimpleNamespace(**base)


def test_fetch_grubhub_menu_swallows_cookies_expired_and_returns_none():
    def _raising_fetcher(url):
        raise GrubhubCookiesExpired("cookies are stale")

    result = fetch_grubhub_menu(_place(), fetcher=_raising_fetcher)
    assert result is None


def test_fetch_grubhub_menu_still_returns_none_on_generic_fetch_error():
    # Regression: a plain fetch error (timeout, parser bug, whatever) must
    # keep behaving exactly as before — only GrubhubCookiesExpired gets the
    # distinct handling.
    def _raising_fetcher(url):
        raise RuntimeError("connection reset")

    result = fetch_grubhub_menu(_place(), fetcher=_raising_fetcher)
    assert result is None


def test_fetch_grubhub_menu_returns_payload_on_success():
    payload = {"object": {"data": {"content": [{"item_id": "1"}]}}}

    def _ok_fetcher(url):
        return payload

    result = fetch_grubhub_menu(_place(), fetcher=_ok_fetcher)
    assert result == payload


def test_default_fetcher_raises_cookies_expired_when_env_var_missing(monkeypatch):
    monkeypatch.delenv("GRUBHUB_COOKIES", raising=False)

    with pytest.raises(GrubhubCookiesExpired):
        _default_fetcher("https://www.grubhub.com/restaurant/some-place/12345")


def test_default_fetcher_raises_cookies_expired_when_env_var_unparseable(monkeypatch):
    # No "=" anywhere and doesn't start with "{" — _load_grubhub_cookies
    # returns an empty dict for this, same as "missing" from the caller's
    # perspective.
    monkeypatch.setenv("GRUBHUB_COOKIES", "not a cookie string at all")

    with pytest.raises(GrubhubCookiesExpired):
        _default_fetcher("https://www.grubhub.com/restaurant/some-place/12345")
