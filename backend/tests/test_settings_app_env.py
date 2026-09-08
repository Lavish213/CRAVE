"""
Coverage for Settings.app_env's normalization of common env-var aliases.

Found in production: a canary run crashed at Settings-load time with a
pydantic ValidationError (before creating its job_runs row) because
Railway's configured APP_ENV was "production", not this app's own
"prod"/"dev"/"staging" vocabulary. Normalizing well-known synonyms here
is more robust than requiring every deploy target's env var to exactly
match this app's internal naming.
"""
from __future__ import annotations

import pytest

from app.config.settings import Settings


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("prod", "prod"),
        ("production", "prod"),
        ("PRODUCTION", "prod"),
        ("Production", "prod"),
        ("dev", "dev"),
        ("development", "dev"),
        ("staging", "staging"),
    ],
)
def test_app_env_accepts_known_aliases(monkeypatch, raw, expected):
    monkeypatch.setenv("APP_ENV", raw)
    assert Settings().app_env == expected


def test_app_env_still_rejects_a_genuinely_invalid_value(monkeypatch):
    monkeypatch.setenv("APP_ENV", "not_a_real_environment")
    with pytest.raises(Exception):
        Settings()


def test_is_prod_true_for_the_production_alias(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    assert Settings().is_prod is True
