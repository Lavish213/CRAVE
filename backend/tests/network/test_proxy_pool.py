"""
Coverage for app.services.network.proxy_pool — used by http_client.py.
This file was 0 bytes before this pass.

The module holds mutable module-level state (_PROXIES, _COOLDOWN,
_FAIL_COUNT), so every test resets it via monkeypatch instead of relying
on import order / test execution order for isolation.

Note: in production _PROXIES ships as a literal empty list ("fill later"
comment in the module) — get_proxy() always returns None until real
proxy entries are configured. These tests monkeypatch in fake proxies to
exercise the cooldown/failure-tracking logic itself.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from app.services.network import proxy_pool


@pytest.fixture(autouse=True)
def _reset_module_state(monkeypatch):
    monkeypatch.setattr(proxy_pool, "_PROXIES", [])
    monkeypatch.setattr(proxy_pool, "_COOLDOWN", {})
    monkeypatch.setattr(proxy_pool, "_FAIL_COUNT", {})


def test_get_proxy_returns_none_when_pool_is_empty():
    assert proxy_pool.get_proxy() is None


def test_get_proxy_returns_a_configured_proxy():
    proxy_pool._PROXIES.append("http://proxy-a:8080")
    assert proxy_pool.get_proxy() == "http://proxy-a:8080"


def test_single_failure_does_not_trigger_cooldown():
    proxy_pool._PROXIES.append("http://proxy-a:8080")
    proxy_pool.report_failure("http://proxy-a:8080")
    assert proxy_pool.get_proxy() == "http://proxy-a:8080"


def test_two_failures_trigger_cooldown_and_exclude_the_proxy():
    proxy_pool._PROXIES.append("http://proxy-a:8080")
    proxy_pool.report_failure("http://proxy-a:8080")
    proxy_pool.report_failure("http://proxy-a:8080")
    assert proxy_pool.get_proxy() is None


def test_get_proxy_excludes_cooling_down_proxy_but_returns_others():
    proxy_pool._PROXIES.extend(["http://proxy-a:8080", "http://proxy-b:8080"])
    proxy_pool.report_failure("http://proxy-a:8080")
    proxy_pool.report_failure("http://proxy-a:8080")
    assert proxy_pool.get_proxy() == "http://proxy-b:8080"


def test_report_success_resets_failure_count_and_clears_cooldown():
    proxy_pool._PROXIES.append("http://proxy-a:8080")
    proxy_pool.report_failure("http://proxy-a:8080")
    proxy_pool.report_failure("http://proxy-a:8080")
    assert proxy_pool.get_proxy() is None  # confirm it's actually in cooldown first

    proxy_pool.report_success("http://proxy-a:8080")

    assert proxy_pool._FAIL_COUNT["http://proxy-a:8080"] == 0
    assert "http://proxy-a:8080" not in proxy_pool._COOLDOWN
    assert proxy_pool.get_proxy() == "http://proxy-a:8080"
