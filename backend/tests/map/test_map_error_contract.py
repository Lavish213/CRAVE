from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.api.v1.routes import map as map_routes


def test_map_route_surfaces_query_failure_as_retryable_503(monkeypatch):
    def fail(**_kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(map_routes, "fetch_places_for_map", fail)

    with pytest.raises(HTTPException) as exc_info:
        map_routes.map_places(
            lat=37.8, lng=-122.27, radius_km=5.0, limit=250,
            city_id=None, category_id=None, db=Mock(), _=None,
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Map temporarily unavailable"


def test_geojson_route_surfaces_query_failure_as_retryable_503(monkeypatch):
    def fail(**_kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(map_routes, "fetch_places_for_map_geojson", fail)

    with pytest.raises(HTTPException) as exc_info:
        map_routes.map_places_geojson(
            lat=37.8, lng=-122.27, radius_km=5.0, limit=250,
            city_id=None, category_id=None, db=Mock(), _=None,
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Map temporarily unavailable"
