from unittest.mock import Mock

from app.services.menu.processing import menu_orchestrator


def test_source_success_requires_public_materialized_rows(monkeypatch):
    record_success = Mock()
    monkeypatch.setattr(
        menu_orchestrator.menu_source_manager,
        "record_success",
        record_success,
    )

    menu_orchestrator.record_materialized_source_success(
        db=Mock(), place_id="place-1", source_url="https://menu.test", published_count=0
    )

    record_success.assert_not_called()


def test_source_success_records_after_publish(monkeypatch):
    record_success = Mock()
    monkeypatch.setattr(
        menu_orchestrator.menu_source_manager,
        "record_success",
        record_success,
    )
    db = Mock()

    menu_orchestrator.record_materialized_source_success(
        db=db, place_id="place-1", source_url="https://menu.test", published_count=4
    )

    record_success.assert_called_once_with(
        db=db, place_id="place-1", source_url="https://menu.test"
    )
