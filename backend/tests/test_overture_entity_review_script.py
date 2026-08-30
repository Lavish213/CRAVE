from __future__ import annotations

import uuid

import pytest

from app.db.models.category import Category, CategoryType
from app.db.models.city import City
from app.db.models.discovery_candidate import DiscoveryCandidate
from app.db.models.place import Place
from app.db.session import SessionLocal
import scripts.apply_overture_entity_review as review


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _candidate(*, row_id: str, external_id: str, name: str, city_id: str):
    return DiscoveryCandidate(
        id=row_id,
        external_id=external_id,
        source="overture",
        name=name,
        city_id=city_id,
        lat=37.79,
        lng=-122.27,
        confidence_score=0.8,
        status="candidate",
        resolved=False,
        blocked=True,
        raw_payload={"canary_batch_id": review.BATCH_ID},
    )


def test_apply_requires_exact_confirmation():
    assert review.execution_is_authorized(
        apply=True,
        confirmation="APPLY_OVERTURE_ENTITY_REVIEW",
    )
    assert not review.execution_is_authorized(
        apply=False,
        confirmation="APPLY_OVERTURE_ENTITY_REVIEW",
    )
    assert not review.execution_is_authorized(apply=True, confirmation="apply")
    assert review.simulation_is_authorized(
        simulate=True,
        confirmation="SIMULATE_OVERTURE_ENTITY_REVIEW",
    )
    assert not review.simulation_is_authorized(
        simulate=True,
        confirmation="simulate",
    )


def test_validate_batch_refuses_identity_drift(db, monkeypatch):
    city_id = str(uuid.uuid4())
    db.add(City(id=city_id, slug=f"test-{city_id}", name="Test City"))
    db.flush()
    row = _candidate(
        row_id=str(uuid.uuid4()),
        external_id="overture:actual",
        name="Actual name",
        city_id=city_id,
    )
    db.add(row)
    db.commit()
    monkeypatch.setattr(
        review,
        "DISPOSITIONS",
        (
            review.Disposition(
                row.id,
                "overture:expected",
                "Expected name",
                "reject_stale",
            ),
        ),
    )

    with pytest.raises(RuntimeError, match="candidate identity changed"):
        review.validate_batch(db)

    db.delete(row)
    db.commit()


def test_apply_review_executes_only_fixed_dispositions(db, monkeypatch):
    city_id = str(uuid.uuid4())
    db.add(City(id=city_id, slug=f"test-{city_id}", name="Test City"))
    db.flush()
    existing = Place(
        id=str(uuid.uuid4()),
        name="Existing Cafe",
        city_id=city_id,
        lat=37.79,
        lng=-122.27,
    )
    alias_target = Place(
        id=str(uuid.uuid4()),
        name="Current Alias Target",
        city_id=city_id,
        lat=37.79,
        lng=-122.27,
    )
    stale = Place(
        id=str(uuid.uuid4()),
        name="Closed Cafe",
        city_id=city_id,
        lat=37.79,
        lng=-122.27,
    )
    category = db.query(Category).filter(Category.slug == "american").one_or_none()
    if category is None:
        category = Category(slug="american", name=f"American {uuid.uuid4()}", type=CategoryType.cuisine)
        db.add(category)

    rows = {
        action: _candidate(
            row_id=str(uuid.uuid4()),
            external_id=f"overture:{uuid.uuid4()}",
            name=f"{action} venue",
            city_id=city_id,
        )
        for action in ("match_existing", "alias_existing", "reject_stale", "promote_new")
    }
    db.add_all([existing, alias_target, stale, *rows.values()])
    db.commit()

    dispositions = (
        review.Disposition(
            rows["match_existing"].id,
            rows["match_existing"].external_id,
            rows["match_existing"].name,
            "match_existing",
            existing_place_id=existing.id,
        ),
        review.Disposition(
            rows["alias_existing"].id,
            rows["alias_existing"].external_id,
            rows["alias_existing"].name,
            "alias_existing",
            existing_place_id=alias_target.id,
            deactivate_place_id=stale.id,
        ),
        review.Disposition(
            rows["reject_stale"].id,
            rows["reject_stale"].external_id,
            rows["reject_stale"].name,
            "reject_stale",
        ),
        review.Disposition(
            rows["promote_new"].id,
            rows["promote_new"].external_id,
            rows["promote_new"].name,
            "promote_new",
            category_slug="american",
        ),
    )
    monkeypatch.setattr(review, "DISPOSITIONS", dispositions)

    new_place_id = str(uuid.uuid4())

    def fake_promote(*, db, candidate_id):
        row = db.get(DiscoveryCandidate, candidate_id)
        place_id = existing.id if candidate_id == rows["match_existing"].id else new_place_id
        if candidate_id == rows["promote_new"].id:
            db.add(
                Place(
                    id=place_id,
                    name=row.name,
                    city_id=city_id,
                    lat=row.lat,
                    lng=row.lng,
                )
            )
        row.resolved = True
        row.resolved_place_id = place_id
        row.status = "promoted"
        return place_id

    monkeypatch.setattr(review, "promote_candidate_v2", fake_promote)

    result = review.apply_review(db)

    assert result == {
        "matched": 1,
        "aliases": 1,
        "rejected": 1,
        "promoted_new": 1,
        "deactivated": 1,
    }
    assert all(row.blocked and row.resolved for row in rows.values())
    assert rows["alias_existing"].resolved_place_id == alias_target.id
    assert rows["reject_stale"].status == "rejected"
    assert rows["promote_new"].category_id == category.id
    assert stale.is_active is False

    db.rollback()
