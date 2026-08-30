"""
Coverage for app.services.discovery.overture_places.fetch_overture_places.

No real S3/network calls here — dataset.to_table() and _latest_release()
are both monkeypatched. Row shapes mirror the real Overture places schema
fields this module actually reads (confirmed live against the real dataset
before writing this code): id, names.primary, categories.primary,
taxonomy.hierarchy, websites, phones, addresses, bbox.
"""
from __future__ import annotations

import io
import pyarrow as pa
import pytest

from app.services.discovery import overture_places
from app.services.discovery.overture_places import fetch_overture_places
from app.services.discovery.promotion_orchestrator_v2 import MIN_CONFIDENCE_THRESHOLD

RESTAURANT_ROW = {
    "id": "08f2a1b2c3d4e5f6",
    "names": {"primary": "Test Restaurant"},
    "categories": {"primary": "restaurant"},
    "taxonomy": {"hierarchy": ["food_and_drink", "restaurant"]},
    "websites": ["example.com"],
    "phones": ["+1 (415) 555-0100"],
    "addresses": [{"freeform": "123 Main St", "locality": "Testville", "postcode": None, "region": None, "country": None}],
    "bbox": {"xmin": -122.4194, "xmax": -122.4194, "ymin": 37.7749, "ymax": 37.7749},
}

BARBER_ROW = {
    "id": "08f2barber000000",
    "names": {"primary": "Not A Restaurant Barbershop"},
    "categories": {"primary": "barber_shop"},
    "taxonomy": {"hierarchy": ["lifestyle_services", "personal_or_beauty_service", "hair_salon"]},
    "websites": [],
    "phones": [],
    "addresses": [],
    "bbox": {"xmin": -122.42, "xmax": -122.42, "ymin": 37.77, "ymax": 37.77},
}


class _FakeDataset:
    def __init__(self, table: pa.Table):
        self._table = table

    def to_table(self, columns=None, filter=None):
        return self._table


def _patch_ok(monkeypatch, rows):
    table = pa.Table.from_pylist(rows)
    monkeypatch.setattr(overture_places, "_latest_release", lambda: "2026-07-22.0")
    monkeypatch.setattr(overture_places.pafs, "S3FileSystem", lambda **kw: object())
    monkeypatch.setattr(overture_places.pads, "dataset", lambda *a, **kw: _FakeDataset(table))


def _bbox_kwargs(**overrides):
    kwargs = dict(lat_min=37.70, lat_max=37.83, lon_min=-122.52, lon_max=-122.35)
    kwargs.update(overrides)
    return kwargs


def test_latest_release_uses_authoritative_stac_latest(monkeypatch):
    class _Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    monkeypatch.setattr(
        overture_places,
        "urlopen",
        lambda _request, timeout: _Response(b'{"latest":"2026-08-19.0"}'),
    )

    assert overture_places._latest_release() == "2026-08-19.0"


def test_fetch_overture_places_surfaces_release_discovery_failure(monkeypatch):
    def _raise():
        raise RuntimeError("no release")

    monkeypatch.setattr(overture_places, "_latest_release", _raise)
    with pytest.raises(RuntimeError, match="no release"):
        fetch_overture_places(**_bbox_kwargs())


def test_fetch_overture_places_surfaces_dataset_exception(monkeypatch):
    monkeypatch.setattr(overture_places, "_latest_release", lambda: "2026-07-22.0")
    monkeypatch.setattr(overture_places.pafs, "S3FileSystem", lambda **kw: object())

    def _raise(*a, **kw):
        raise RuntimeError("s3 unreachable")

    monkeypatch.setattr(overture_places.pads, "dataset", _raise)
    with pytest.raises(RuntimeError, match="dataset fetch failed"):
        fetch_overture_places(**_bbox_kwargs())


def test_fetch_overture_places_maps_fields_correctly(monkeypatch):
    _patch_ok(monkeypatch, [RESTAURANT_ROW])
    results = fetch_overture_places(**_bbox_kwargs())

    assert len(results) == 1
    r = results[0]
    assert r["external_id"] == "overture:08f2a1b2c3d4e5f6"
    assert r["name"] == "Test Restaurant"
    assert r["address"] == "123 Main St, Testville"
    assert r["lat"] == pytest.approx(37.7749)
    assert r["lon"] == pytest.approx(-122.4194)
    assert r["phone"] == "+14155550100"
    assert r["website"] == "https://example.com"
    assert r["category_hint"] == "restaurant"
    assert r["source"] == "overture"


def test_fetch_overture_places_confidence_clears_the_promotion_threshold(monkeypatch):
    """The specific bug fixed for OSM this session — deliberately locked in
    here too, so this second source doesn't repeat it."""
    _patch_ok(monkeypatch, [RESTAURANT_ROW])
    results = fetch_overture_places(**_bbox_kwargs())
    assert results[0]["confidence"] >= MIN_CONFIDENCE_THRESHOLD


def test_fetch_overture_places_excludes_non_food_categories(monkeypatch):
    _patch_ok(monkeypatch, [RESTAURANT_ROW, BARBER_ROW])
    results = fetch_overture_places(**_bbox_kwargs())

    names = [r["name"] for r in results]
    assert "Test Restaurant" in names
    assert "Not A Restaurant Barbershop" not in names


def test_fetch_overture_places_skips_rows_without_a_name(monkeypatch):
    row = {**RESTAURANT_ROW, "names": {"primary": None}}
    _patch_ok(monkeypatch, [row])
    assert fetch_overture_places(**_bbox_kwargs()) == []


def test_fetch_overture_places_handles_missing_website_phone_address(monkeypatch):
    row = {
        **RESTAURANT_ROW,
        "websites": [],
        "phones": [],
        "addresses": [],
    }
    _patch_ok(monkeypatch, [row])
    results = fetch_overture_places(**_bbox_kwargs())

    assert len(results) == 1
    assert results[0]["website"] is None
    assert results[0]["phone"] is None
    assert results[0]["address"] is None
