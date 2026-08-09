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
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_crave.db")
os.environ.setdefault("APP_ENV", "dev")
# app.services.upload.r2_client.generate_public_url() raises if this is
# unset (see that module — it deliberately no longer falls back to the
# private S3 API endpoint). Tests that exercise the real upload pipeline
# with a mocked S3 client still call the real generate_public_url(), so
# it needs *some* value; the actual URL content doesn't matter for tests.
os.environ.setdefault("R2_PUBLIC_BASE_URL", "https://pub-test.r2.dev")

from app.db.session import engine  # noqa: E402
from app.db.models import Base  # noqa: E402

Base.metadata.create_all(bind=engine)

# ---------------------------------------------------------------------------
# Seed a minimal city + place so tests that need "active places in DB" don't
# skip. Idempotent — re-running the suite won't duplicate the row.
# ---------------------------------------------------------------------------
import pytest  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.db.models.city import City  # noqa: E402
from app.db.models.place import Place  # noqa: E402

_SEED_CITY_ID = "00000000-0000-0000-0000-000000000001"
_SEED_PLACE_ID = "00000000-0000-0000-0000-000000000002"


def _seed_db() -> None:
    db: Session = SessionLocal()
    try:
        if not db.get(City, _SEED_CITY_ID):
            db.add(City(
                id=_SEED_CITY_ID,
                name="Test City",
                slug="test-city",
                lat=37.8044,
                lng=-122.2712,
                is_active=True,
            ))
        if not db.get(Place, _SEED_PLACE_ID):
            p = Place(
                id=_SEED_PLACE_ID,
                name="Test Place",
                city_id=_SEED_CITY_ID,
                lat=37.8044,
                lng=-122.2712,
                is_active=True,
                rank_score=0.75,
            )
            db.add(p)
        db.commit()
    finally:
        db.close()


_seed_db()
