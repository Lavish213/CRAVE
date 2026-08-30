from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest

from app.db.models.discovery_candidate import DiscoveryCandidate
from app.db.session import SessionLocal

from scripts.run_overture_canary import (
    _assess_nearby,
    _batch_query,
    _distance_m,
    _names_likely_match,
    _rollback,
    execution_is_authorized,
    rollback_is_authorized,
)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_stage_requires_exact_confirmation():
    assert execution_is_authorized(stage=True, confirmation="STAGE_OVERTURE")
    assert not execution_is_authorized(stage=False, confirmation="STAGE_OVERTURE")
    assert not execution_is_authorized(stage=True, confirmation="stage_overture")


def test_rollback_requires_batch_and_exact_confirmation():
    assert rollback_is_authorized(
        batch_id="oakland-20260830-a",
        confirmation="ROLLBACK_OVERTURE",
    )
    assert not rollback_is_authorized(batch_id=None, confirmation="ROLLBACK_OVERTURE")
    assert not rollback_is_authorized(batch_id="batch", confirmation="ROLLBACK")


def test_distance_and_near_duplicate_classification():
    distance = _distance_m(37.8044, -122.2712, 37.8045, -122.2712)
    assert 10 < distance < 12

    record = {"name": "Cafe Example", "lat": 37.8044, "lon": -122.2712}
    place = SimpleNamespace(
        id="place-1",
        name="Café Example",
        lat=37.8045,
        lng=-122.2712,
    )
    result = _assess_nearby(record, [place])

    assert result.nearest_place_id == "place-1"
    assert result.nearest_distance_m is not None
    assert result.same_name_within_100m is True
    assert result.likely_duplicate_within_100m is True


def test_name_match_flags_brand_variants_without_merging_unrelated_neighbors():
    assert _names_likely_match("NIDO", "NIDO Kitchen & Bar")
    assert _names_likely_match(
        "Good Vybes and Brews",
        "Good Vybes & Brews | Speciality Coffee and Tea",
    )
    assert not _names_likely_match("Tiger's Taproom", "North Beach Sandwicheez")


def test_rollback_removes_only_blocked_unresolved_rows_from_exact_batch(db):
    batch_id = f"test-{uuid.uuid4()}"
    rows = [
        DiscoveryCandidate(
            name="Rollback target",
            city_id="00000000-0000-0000-0000-000000000001",
            source="overture",
            external_id=f"overture:{uuid.uuid4()}",
            confidence_score=0.8,
            status="candidate",
            blocked=True,
            resolved=False,
            raw_payload={
                "canary_marker": "overture_population_canary",
                "canary_batch_id": batch_id,
            },
        ),
        DiscoveryCandidate(
            name="Different batch",
            city_id="00000000-0000-0000-0000-000000000001",
            source="overture",
            external_id=f"overture:{uuid.uuid4()}",
            confidence_score=0.8,
            status="candidate",
            blocked=True,
            resolved=False,
            raw_payload={
                "canary_marker": "overture_population_canary",
                "canary_batch_id": f"other-{uuid.uuid4()}",
            },
        ),
        DiscoveryCandidate(
            name="Released row",
            city_id="00000000-0000-0000-0000-000000000001",
            source="overture",
            external_id=f"overture:{uuid.uuid4()}",
            confidence_score=0.8,
            status="candidate",
            blocked=False,
            resolved=False,
            raw_payload={
                "canary_marker": "overture_population_canary",
                "canary_batch_id": batch_id,
            },
        ),
    ]
    db.add_all(rows)
    db.commit()
    ids = [row.id for row in rows]

    result = _rollback(db, batch_id)

    assert result == {"batch_id": batch_id, "rolled_back": 1}
    remaining = {
        row.id for row in db.query(DiscoveryCandidate).filter(
            DiscoveryCandidate.id.in_(ids)
        )
    }
    assert remaining == {rows[1].id, rows[2].id}
    assert _batch_query(db, batch_id).count() == 1

    db.query(DiscoveryCandidate).filter(DiscoveryCandidate.id.in_(ids)).delete(
        synchronize_session=False
    )
    db.commit()
