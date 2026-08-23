"""
Coverage for app.db.session._build_engine's Postgres pool sizing.

Regression test for a real production risk: pool_size/max_overflow used to
be hardcoded (20/40 -- 60 max connections per process). Once the scheduler
became a separate Railway service (see settings.py's run_embedded_scheduler
comment), that meant two processes each independently maintaining up to 60
connections against the same database -- 120 combined, already over
Railway Postgres's default max_connections of 100 on its own, before
counting Alembic, the Console, or Postgres's own reserved connections.
Now configurable via settings.db_pool_size/db_max_overflow so each Railway
service can be tuned independently without a code change.
"""
from __future__ import annotations

from app.config.settings import settings
from app.db.session import _build_engine


def test_postgres_engine_uses_configured_pool_settings(monkeypatch):
    monkeypatch.setattr(settings, "database_url", "postgresql://user:pass@localhost:5432/testdb")
    monkeypatch.setattr(settings, "db_pool_size", 7)
    monkeypatch.setattr(settings, "db_max_overflow", 3)

    engine = _build_engine()

    assert engine.pool.size() == 7
    assert engine.pool._max_overflow == 3


def test_postgres_engine_default_pool_settings_stay_conservative():
    # Guards against silently reintroducing a large hardcoded default --
    # combined across web + worker services, this has to comfortably fit
    # under Railway Postgres's default max_connections (100).
    assert settings.db_pool_size <= 15
    assert settings.db_max_overflow <= 15
