"""
Coverage for GET /api/v1/craves/reasoned -- the Craves Screen Contract's
"reasoned subset" (docs/doctrine/CRAVE_SCREEN_CONTRACT_CRAVES.md §5/§6/
§9/§10): the same build_decision_session() engine Decision Session uses,
scoped to this user's saved pool (native saves + manually-added entries
in HitlistSave, and matched imported/social CraveItems) instead of a
city/radius fetch, with any visit-evidence tier graduating a place out
of the candidate pool. Role-selection logic itself is covered by
test_decision_session_builder.py; this file only covers this route's own
candidate retrieval and graduation.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.category import Category
from app.db.models.hitlist_save import HitlistSave
from app.db.models.crave_item import CraveItem
from app.db.models.visit_evidence import VisitEvidence, VISIT_TIER_INFERRED

client = TestClient(app)


def _as_user(user_id: str):
    app.dependency_overrides[get_current_user_id] = lambda: user_id


@pytest.fixture(autouse=True)
def _overrides():
    app.dependency_overrides[rate_limit] = lambda: None
    yield
    app.dependency_overrides.pop(rate_limit, None)
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest.fixture
def db():
    session = SessionLocal()
    # ImageWorker's own starvation-fairness test (test_image_worker_
    # starvation.py) queries the entire places table and asserts on an
    # exact expected count of places "needing image work" -- any place
    # this file creates and leaves behind pollutes that count for
    # whichever test runs later in the same pytest session/DB. Track and
    # delete every place this file creates so no test order or DB
    # lifetime assumption elsewhere in the suite is affected by this one.
    created_place_ids: list[str] = []
    session._craves_test_created_place_ids = created_place_ids  # type: ignore[attr-defined]
    try:
        yield session
    finally:
        if created_place_ids:
            session.rollback()
            session.query(Place).filter(Place.id.in_(created_place_ids)).delete(synchronize_session=False)
            session.commit()
        session.close()


def _make_city(db) -> str:
    city_id = str(uuid.uuid4())
    db.add(City(id=city_id, name="Craves City", slug=f"craves-city-{city_id[:8]}",
                lat=37.0, lng=-122.0, is_active=True))
    db.commit()
    return city_id


def _make_place(db, city_id: str, *, name: str, score: float, category: Category | None = None) -> Place:
    p = Place(
        id=str(uuid.uuid4()), name=name, city_id=city_id,
        lat=37.0, lng=-122.0, is_active=True, rank_score=score,
    )
    if category:
        p.categories.append(category)
    db.add(p)
    db.commit()
    db._craves_test_created_place_ids.append(p.id)
    return p


def _make_category(db, name: str) -> Category:
    existing = db.query(Category).filter(Category.name == name).first()
    if existing:
        return existing
    cat = Category(slug=name.lower(), name=name)
    db.add(cat)
    db.commit()
    return cat


def test_returns_no_cards_when_nothing_saved(db):
    _as_user(f"user-{uuid.uuid4()}")
    resp = client.get("/api/v1/craves/reasoned")
    assert resp.status_code == 200
    assert resp.json() == {"cards": [], "degraded": True}


def test_includes_a_native_save_in_the_candidate_pool(db):
    user_id = f"user-{uuid.uuid4()}"
    _as_user(user_id)
    city_id = _make_city(db)
    cat = _make_category(db, f"CravesCat-{uuid.uuid4().hex[:8]}")
    native = _make_place(db, city_id, name="Native Save", score=0.5, category=cat)

    db.add(HitlistSave(
        user_id=user_id, place_name=native.name, place_id=native.id,
        dedup_key=f"save:{user_id}:{native.id}",
    ))
    db.commit()

    resp = client.get("/api/v1/craves/reasoned")
    assert resp.status_code == 200
    returned_ids = {c["place"]["id"] for c in resp.json()["cards"]}
    assert native.id in returned_ids


def test_includes_a_matched_imported_crave_in_the_candidate_pool(db):
    """Contract §9: a matched imported/social-matched CraveItem feeds the
    same reasoned subset as a native save, once resolved to a real place --
    no scoring difference between the two evidence types."""
    user_id = f"user-{uuid.uuid4()}"
    _as_user(user_id)
    city_id = _make_city(db)
    cat = _make_category(db, f"CravesCat-{uuid.uuid4().hex[:8]}")
    imported = _make_place(db, city_id, name="Imported Match", score=0.5, category=cat)

    crave = CraveItem(url="https://tiktok.com/example", submitted_by=user_id)
    crave.matched_place_id = imported.id
    crave.status = "matched"
    db.add(crave)
    db.commit()

    resp = client.get("/api/v1/craves/reasoned")
    assert resp.status_code == 200
    returned_ids = {c["place"]["id"] for c in resp.json()["cards"]}
    assert imported.id in returned_ids


def test_a_graduated_place_with_any_visit_tier_is_excluded(db):
    user_id = f"user-{uuid.uuid4()}"
    _as_user(user_id)
    city_id = _make_city(db)
    cat = _make_category(db, f"CravesCat-{uuid.uuid4().hex[:8]}")

    graduated = _make_place(db, city_id, name="Already Visited", score=0.9, category=cat)
    still_active = _make_place(db, city_id, name="Not Yet Visited", score=0.5, category=cat)

    db.add(HitlistSave(
        user_id=user_id, place_name=graduated.name, place_id=graduated.id,
        dedup_key=f"save:{user_id}:{graduated.id}",
    ))
    db.add(HitlistSave(
        user_id=user_id, place_name=still_active.name, place_id=still_active.id,
        dedup_key=f"save:{user_id}:{still_active.id}",
    ))
    # Contract §10: even the loosest tier (inferred) graduates a place --
    # not just declared/verified (Rank Home's stricter bar).
    db.add(VisitEvidence(
        user_id=user_id, place_id=graduated.id, tier=VISIT_TIER_INFERRED,
        source="test_fixture", source_ref="fixture-1",
        occurred_at=datetime.now(timezone.utc),
    ))
    db.commit()

    resp = client.get("/api/v1/craves/reasoned")
    assert resp.status_code == 200
    returned_ids = {c["place"]["id"] for c in resp.json()["cards"]}
    assert graduated.id not in returned_ids
    assert still_active.id in returned_ids


def test_reasoned_subset_reuses_decision_session_role_vocabulary(db):
    """Confirmed product decision: Craves' Reason Block reuses Decision
    Session's exact role labels (best_fit/safe_bet/wildcard) since it is
    the literal same engine over a different candidate set, not a
    conceptually distinct surface the way Search is (contract §13:
    distinguished only by analytics `surface`, not by vocabulary)."""
    user_id = f"user-{uuid.uuid4()}"
    _as_user(user_id)
    city_id = _make_city(db)
    cat = _make_category(db, f"CravesCat-{uuid.uuid4().hex[:8]}")
    best = _make_place(db, city_id, name="Top Saved Pick", score=0.9, category=cat)

    db.add(HitlistSave(
        user_id=user_id, place_name=best.name, place_id=best.id,
        dedup_key=f"save:{user_id}:{best.id}",
    ))
    db.commit()

    resp = client.get("/api/v1/craves/reasoned")
    assert resp.status_code == 200
    roles = {c["role"] for c in resp.json()["cards"]}
    assert roles <= {"best_fit", "safe_bet", "wildcard"}
    assert "best_fit" in roles


def test_an_inactive_place_is_never_returned(db):
    user_id = f"user-{uuid.uuid4()}"
    _as_user(user_id)
    city_id = _make_city(db)
    inactive = Place(
        id=str(uuid.uuid4()), name="Closed Down", city_id=city_id,
        lat=37.0, lng=-122.0, is_active=False, rank_score=0.9,
    )
    db.add(inactive)
    db.commit()
    db._craves_test_created_place_ids.append(inactive.id)
    db.add(HitlistSave(
        user_id=user_id, place_name=inactive.name, place_id=inactive.id,
        dedup_key=f"save:{user_id}:{inactive.id}",
    ))
    db.commit()

    resp = client.get("/api/v1/craves/reasoned")
    assert resp.status_code == 200
    assert resp.json() == {"cards": [], "degraded": True}
