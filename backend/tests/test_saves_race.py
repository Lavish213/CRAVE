"""
Regression coverage for a real race in POST /saves.

create_save did a check-then-insert (query for an existing HitlistSave by
(user_id, dedup_key), then add + commit) with no try/except around the
commit. HitlistSave has a real unique constraint
(uq_hitlist_saves_user_dedup), so two near-simultaneous requests for the
same user/place -- a double-tap on the Save button, or a client retry
after a timed-out first request, both routine on mobile -- would make the
second commit raise an unhandled IntegrityError, surfacing as a bare 500
instead of the intended idempotent {"status": "already_saved"}.

This is the same bug class moderation.py's report_image/report_video/
report_place endpoints already guard against with try/except
IntegrityError: db.rollback(); return {"status": "already_reported"}.
create_save now does the same.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.hitlist_save import HitlistSave

client = TestClient(app)


def _as_user(user_id: str):
    app.dependency_overrides[get_current_user_id] = lambda: user_id


@pytest.fixture(autouse=True)
def _overrides():
    app.dependency_overrides[rate_limit] = lambda: None
    yield
    app.dependency_overrides.pop(get_current_user_id, None)
    app.dependency_overrides.pop(rate_limit, None)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def city_and_place(db):
    city_id = str(uuid.uuid4())
    db.add(City(
        id=city_id, name="Save Race Test City",
        slug=f"save-race-test-city-{city_id[:8]}",
        lat=37.0, lng=-122.0, is_active=True,
    ))
    place = Place(
        id=str(uuid.uuid4()), name="Save Race Test Place", city_id=city_id,
        lat=37.0, lng=-122.0, is_active=True, rank_score=0.5,
    )
    db.add(place)
    db.commit()
    yield place
    db.query(HitlistSave).filter(HitlistSave.place_id == place.id).delete(
        synchronize_session=False
    )
    db.query(Place).filter(Place.id == place.id).delete(synchronize_session=False)
    db.query(City).filter(City.id == city_id).delete(synchronize_session=False)
    db.commit()


def test_create_save_race_returns_already_saved_not_500(monkeypatch, city_and_place):
    """
    Simulates the race deterministically: an independent session commits
    the "other" request's row in between this request's own existence
    check and its own commit, so this request's commit collides with a
    real unique-constraint violation rather than a contrived one.
    """
    from app.api.v1.routes import saves as saves_module

    place = city_and_place
    user_id = f"race-user-{uuid.uuid4().hex[:8]}"
    _as_user(user_id)

    real_clear = saves_module._clear_share_auto_save_opt_out
    winner_id = str(uuid.uuid4())
    calls = {"count": 0}

    def _racing_clear(db, user_id_, place_id_):
        calls["count"] += 1
        if calls["count"] == 1:
            # Only inject the race on the first call (right before this
            # request's own commit attempt) -- the second call happens
            # during this request's own recovery path and must behave
            # normally, not re-trigger the race against itself.
            other = SessionLocal()
            try:
                other.add(HitlistSave(
                    id=winner_id,
                    user_id=user_id_,
                    place_name=place.name,
                    place_id=place_id_,
                    resolution_status="resolved",
                    dedup_key=f"save:{user_id_}:{place_id_}",
                ))
                other.commit()
            finally:
                other.close()
        return real_clear(db, user_id_, place_id_)

    monkeypatch.setattr(saves_module, "_clear_share_auto_save_opt_out", _racing_clear)

    resp = client.post("/api/v1/saves", json={"place_id": place.id})

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "already_saved"
    assert body["id"] == winner_id

    # Exactly one HitlistSave row exists for this user/place -- the loser's
    # insert was rolled back, not left as a duplicate or an orphaned attempt.
    rows = (
        SessionLocal()
        .query(HitlistSave)
        .filter(
            HitlistSave.user_id == user_id,
            HitlistSave.place_id == place.id,
        )
        .all()
    )
    assert len(rows) == 1
    assert rows[0].id == winner_id


def test_create_save_still_saves_normally_without_a_race(city_and_place):
    """Sanity check the happy path is untouched by the race-handling change."""
    place = city_and_place
    user_id = f"normal-user-{uuid.uuid4().hex[:8]}"
    _as_user(user_id)

    resp = client.post("/api/v1/saves", json={"place_id": place.id})

    assert resp.status_code == 201
    assert resp.json()["status"] == "saved"

    # A second call for the same user/place is the pre-existing idempotent
    # fast path (found before ever reaching the insert), not the race path.
    resp2 = client.post("/api/v1/saves", json={"place_id": place.id})
    assert resp2.status_code == 201
    assert resp2.json()["status"] == "already_saved"
