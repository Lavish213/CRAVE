from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.api.v1.routes import search as search_route
from app.services.query.places_query import list_places


def test_search_query_failure_is_not_reported_as_empty_results(monkeypatch):
    def fail_search(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(search_route, "execute_search", fail_search)

    with pytest.raises(HTTPException) as exc_info:
        search_route.search(
            query="pizza",
            city_id=None,
            category_id=None,
            price_tier=None,
            lat=None,
            lng=None,
            page=1,
            page_size=20,
            db=Mock(),
            _=None,
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Search temporarily unavailable"


def test_place_list_query_failure_reaches_the_route_error_handler():
    db = Mock()
    db.query.side_effect = RuntimeError("database unavailable")

    with pytest.raises(RuntimeError, match="database unavailable"):
        list_places(db, city_id=None, limit=20, offset=0)
