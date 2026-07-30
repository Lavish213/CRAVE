"""
Coverage for app.services.network.session_identity — used by
http_client.py. This file was 0 bytes before this pass.

_SESSIONS is mutable module-level state, so every test resets it via
monkeypatch instead of relying on test execution order for isolation.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from app.services.network import session_identity


@pytest.fixture(autouse=True)
def _reset_module_state(monkeypatch):
    monkeypatch.setattr(session_identity, "_SESSIONS", {})


def test_get_identity_returns_a_populated_identity():
    identity = session_identity.get_identity("example.com")
    assert identity.id
    assert identity.user_agent == session_identity.DEFAULT_UA
    assert identity.proxy is None


def test_get_identity_is_cached_per_host():
    first = session_identity.get_identity("example.com")
    second = session_identity.get_identity("example.com")
    assert first is second
    assert first.id == second.id


def test_get_identity_differs_across_hosts():
    a = session_identity.get_identity("example.com")
    b = session_identity.get_identity("other.com")
    assert a.id != b.id


def test_reset_identity_forces_a_new_identity_on_next_call():
    original = session_identity.get_identity("example.com")
    session_identity.reset_identity("example.com")
    refreshed = session_identity.get_identity("example.com")
    assert refreshed.id != original.id


def test_reset_identity_is_a_noop_for_an_unknown_host():
    # Must not raise even though "never-seen.com" was never cached.
    session_identity.reset_identity("never-seen.com")
