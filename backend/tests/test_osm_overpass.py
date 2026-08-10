"""
Coverage for osm_overpass.py's fetch_osm_pois — specifically locks in the
confidence value each returned candidate carries, since that value is what
determines whether promotion_orchestrator_v2 ever promotes it at all.

Regression test for a real, confirmed production bug: confidence was 0.6,
strictly below MIN_CONFIDENCE_THRESHOLD (0.72) in promotion_orchestrator_v2.py,
and candidate_store_v2's max()-merge for automated sources (OSM never passes
a contributor_key) means that value never grows via re-scans. Every OSM
candidate was therefore permanently stuck in discovery_candidates — ingested
nightly, never promoted, never backfilling Place.website on a matched place.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.discovery.osm_overpass import fetch_osm_pois
from app.services.discovery.promotion_orchestrator_v2 import MIN_CONFIDENCE_THRESHOLD

SAMPLE_ELEMENT = {
    "type": "node",
    "id": 12345,
    "lat": 51.5074,
    "lon": -0.1278,
    "tags": {
        "name": "Test Restaurant",
        "amenity": "restaurant",
        "addr:housenumber": "1",
        "addr:street": "Main St",
        "addr:city": "London",
        "phone": "+44 20 1234 5678",
        "website": "example.com",
        "cuisine": "italian",
    },
}


def _mock_response(status_code=200, elements=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {"elements": elements or []}
    return resp


def test_fetch_osm_pois_confidence_clears_the_promotion_threshold():
    """The actual regression: OSM's confidence must be high enough for
    promotion_orchestrator_v2 to ever pick these candidates up."""
    with patch(
        "app.services.discovery.osm_overpass.fetch",
        return_value=_mock_response(elements=[SAMPLE_ELEMENT]),
    ):
        results = fetch_osm_pois(lat_min=51.4, lat_max=51.6, lon_min=-0.2, lon_max=-0.1)

    assert len(results) == 1
    assert results[0]["confidence"] >= MIN_CONFIDENCE_THRESHOLD


def test_fetch_osm_pois_maps_fields_correctly():
    with patch(
        "app.services.discovery.osm_overpass.fetch",
        return_value=_mock_response(elements=[SAMPLE_ELEMENT]),
    ):
        results = fetch_osm_pois(lat_min=51.4, lat_max=51.6, lon_min=-0.2, lon_max=-0.1)

    record = results[0]
    assert record["external_id"] == "osm:node:12345"
    assert record["name"] == "Test Restaurant"
    assert record["address"] == "1 Main St London"
    assert record["phone"] == "+442012345678"
    assert record["website"] == "https://example.com"
    assert record["category_hint"] == "restaurant"
    assert record["source"] == "osm"


def test_fetch_osm_pois_skips_elements_without_name():
    element = {**SAMPLE_ELEMENT, "tags": {**SAMPLE_ELEMENT["tags"], "name": ""}}
    with patch(
        "app.services.discovery.osm_overpass.fetch",
        return_value=_mock_response(elements=[element]),
    ):
        results = fetch_osm_pois(lat_min=51.4, lat_max=51.6, lon_min=-0.2, lon_max=-0.1)

    assert results == []


def test_fetch_osm_pois_skips_elements_without_coordinates():
    element = {**SAMPLE_ELEMENT, "lat": None, "lon": None}
    element.pop("center", None)
    with patch(
        "app.services.discovery.osm_overpass.fetch",
        return_value=_mock_response(elements=[element]),
    ):
        results = fetch_osm_pois(lat_min=51.4, lat_max=51.6, lon_min=-0.2, lon_max=-0.1)

    assert results == []


def test_fetch_osm_pois_returns_empty_on_non_200():
    with patch(
        "app.services.discovery.osm_overpass.fetch",
        return_value=_mock_response(status_code=500),
    ):
        results = fetch_osm_pois(lat_min=51.4, lat_max=51.6, lon_min=-0.2, lon_max=-0.1)

    assert results == []


def test_fetch_osm_pois_returns_empty_on_fetch_exception():
    with patch(
        "app.services.discovery.osm_overpass.fetch",
        side_effect=RuntimeError("connection reset"),
    ):
        results = fetch_osm_pois(lat_min=51.4, lat_max=51.6, lon_min=-0.2, lon_max=-0.1)

    assert results == []


def test_fetch_osm_pois_reads_center_coordinates_for_ways():
    """Ways/relations report their location under 'center', not top-level lat/lon."""
    element = {
        "type": "way",
        "id": 999,
        "center": {"lat": 51.5, "lon": -0.13},
        "tags": {"name": "Way Restaurant", "amenity": "cafe"},
    }
    with patch(
        "app.services.discovery.osm_overpass.fetch",
        return_value=_mock_response(elements=[element]),
    ):
        results = fetch_osm_pois(lat_min=51.4, lat_max=51.6, lon_min=-0.2, lon_max=-0.1)

    assert len(results) == 1
    assert results[0]["lat"] == 51.5
    assert results[0]["lon"] == -0.13
