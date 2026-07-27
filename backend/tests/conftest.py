"""
Shared pytest setup for the whole backend/tests/ tree.

Without this, every route-level test that touches the database fails
immediately with "no such table: ..." — nothing in the app ever calls
Base.metadata.create_all() (schema is normally applied via Alembic against
a real Postgres instance), so a bare fresh SQLite file has zero tables.

Two things have to happen, in this order, before any test module imports
app.main:
  1. DATABASE_URL must point at a throwaway file, not the real dev app.db —
     otherwise running the suite locally would create/pollute your actual
     local database.
  2. The schema must be created against that file.

Both must happen as bare module-level code (not inside a fixture): pytest
imports every test_*.py during collection, BEFORE any fixture runs, and
app.db.session builds its SQLAlchemy `engine` at import time from whatever
DATABASE_URL is set at that moment. A fixture here would run too late —
by then every test module's `from app.main import app` has already bound
the engine to whichever database was configured at import time.

CI sets DATABASE_URL explicitly before invoking pytest (see
.github/workflows/ci.yml) so this only acts as a safety net for local runs.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_crave.db")
os.environ.setdefault("APP_ENV", "dev")

from app.db.session import engine  # noqa: E402
from app.db.models import Base  # noqa: E402

Base.metadata.create_all(bind=engine)
