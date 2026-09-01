"""
Coverage for scripts/run_phase4_batch.py's safety gate -- added after
finding this script had NO confirmation/preview step and NO cap at all
(omitting --limit ran against every matching place), unlike
run_menu_backlog_canary.py's preview-by-default + exact-confirm-count
discipline. It drives MasterDataOrchestrator -> ExtractionController, a
materially less-guarded extraction path than menu_extraction_router.py.
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place

from scripts.run_phase4_batch import MAX_BATCH_SIZE, main


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def place_needing_menu(db):
    city = City(
        id=str(uuid.uuid4()), name="Phase4 Gate Test City",
        slug=f"phase4-gate-test-{uuid.uuid4().hex[:8]}", lat=37.8, lng=-122.27, is_active=True,
    )
    db.add(city)
    db.flush()
    place = Place(
        name="Phase4 Gate Test Place", city_id=city.id, is_active=True,
        website="https://example.test",
    )
    db.add(place)
    db.commit()
    yield place
    db.query(Place).filter(Place.id == place.id).delete()
    db.query(City).filter(City.id == city.id).delete()
    db.commit()


def test_refuses_without_a_limit(capsys):
    assert main([]) == 2
    assert "Refused" in capsys.readouterr().err


def test_refuses_a_limit_above_the_cap(capsys):
    assert main(["--limit", str(MAX_BATCH_SIZE + 1)]) == 2
    assert "Refused" in capsys.readouterr().err


def test_preview_mode_never_touches_master_data_orchestrator(place_needing_menu, capsys):
    """Without --run, this must be read-only -- no place should ever be
    processed by MasterDataOrchestrator just from a preview."""
    with patch("scripts.run_phase4_batch.MasterDataOrchestrator") as mock_orch:
        main(["--limit", "5", "--priority", "web"])

    mock_orch.assert_not_called()
    assert "Preview only" in capsys.readouterr().out


def test_run_flag_actually_invokes_the_orchestrator(place_needing_menu):
    with patch("scripts.run_phase4_batch.MasterDataOrchestrator") as mock_orch_cls:
        mock_orch_cls.return_value.ensure_place.return_value = type(
            "R", (), {
                "menu_action": "skipped", "menu_items_after": 0, "menu_items_before": 0,
                "menu_fallback_used": False, "item_images_bridged": 0,
                "menu_strategy": None, "menu_blocked_reason": None,
            },
        )()
        main(["--limit", "5", "--priority", "web", "--run"])

    mock_orch_cls.return_value.ensure_place.assert_called()
