"""
Coverage for app.core.contributor_access -- the shared admin/trusted-
contributor allowlists used by moderation.py's review gate and
upload_moderation.py's contributor-tier upload gate.
"""
from __future__ import annotations

from app.core import contributor_access as ca


def test_admin_ids_parses_comma_separated_list(monkeypatch):
    monkeypatch.setenv("ADMIN_USER_IDS", "user-1, user-2 ,user-3")
    assert ca.admin_ids() == {"user-1", "user-2", "user-3"}


def test_admin_ids_empty_when_unset(monkeypatch):
    monkeypatch.delenv("ADMIN_USER_IDS", raising=False)
    assert ca.admin_ids() == set()


def test_admin_ids_ignores_blank_entries(monkeypatch):
    monkeypatch.setenv("ADMIN_USER_IDS", "  , ,user-1,")
    assert ca.admin_ids() == {"user-1"}


def test_is_admin_true_for_listed_user(monkeypatch):
    monkeypatch.setenv("ADMIN_USER_IDS", "admin-1")
    assert ca.is_admin("admin-1") is True
    assert ca.is_admin("someone-else") is False


def test_is_admin_false_for_none(monkeypatch):
    monkeypatch.setenv("ADMIN_USER_IDS", "admin-1")
    assert ca.is_admin(None) is False


def test_trusted_contributor_ids_parses_comma_separated_list(monkeypatch):
    monkeypatch.setenv("TRUSTED_CONTRIBUTOR_USER_IDS", "staff-1,staff-2")
    assert ca.trusted_contributor_ids() == {"staff-1", "staff-2"}


def test_is_trusted_contributor_true_for_admin(monkeypatch):
    monkeypatch.setenv("ADMIN_USER_IDS", "admin-1")
    monkeypatch.delenv("TRUSTED_CONTRIBUTOR_USER_IDS", raising=False)
    assert ca.is_trusted_contributor("admin-1") is True


def test_is_trusted_contributor_true_for_explicit_trusted_contributor(monkeypatch):
    monkeypatch.delenv("ADMIN_USER_IDS", raising=False)
    monkeypatch.setenv("TRUSTED_CONTRIBUTOR_USER_IDS", "influencer-1")
    assert ca.is_trusted_contributor("influencer-1") is True


def test_is_trusted_contributor_false_for_plain_user(monkeypatch):
    monkeypatch.setenv("ADMIN_USER_IDS", "admin-1")
    monkeypatch.setenv("TRUSTED_CONTRIBUTOR_USER_IDS", "influencer-1")
    assert ca.is_trusted_contributor("random-user") is False


def test_is_trusted_contributor_fails_closed_when_both_unset(monkeypatch):
    monkeypatch.delenv("ADMIN_USER_IDS", raising=False)
    monkeypatch.delenv("TRUSTED_CONTRIBUTOR_USER_IDS", raising=False)
    assert ca.is_trusted_contributor("anyone") is False


def test_is_trusted_contributor_false_for_none():
    assert ca.is_trusted_contributor(None) is False
