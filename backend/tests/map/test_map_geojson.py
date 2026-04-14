# tests/map/test_map_geojson.py
import sys
from pathlib import Path

# Add backend to path to allow imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from app.api.v1.schemas.map import GeoJSONFeatureCollection, GeoJSONFeature, GeoJSONGeometry, GeoJSONProperties

def test_geojson_feature_collection_structure():
    fc = GeoJSONFeatureCollection(features=[
        GeoJSONFeature(
            geometry=GeoJSONGeometry(coordinates=[-122.41, 37.77]),
            properties=GeoJSONProperties(
                id="abc", name="Test", tier="elite",
                rank_score=0.85, price_tier=2,
                primary_image_url=None, has_menu=True,
            ),
        )
    ])
    assert fc.type == "FeatureCollection"
    assert len(fc.features) == 1
    assert fc.features[0].type == "Feature"
    assert fc.features[0].geometry.type == "Point"
    assert fc.features[0].geometry.coordinates == [-122.41, 37.77]
    assert fc.features[0].properties.tier == "elite"

def test_geojson_properties_tier_values():
    for tier in ("elite", "trusted", "solid", "default"):
        props = GeoJSONProperties(
            id="x", name="X", tier=tier, rank_score=0.5,
        )
        assert props.tier == tier

from app.services.query.map_query import _compute_tier_thresholds, _assign_tier

def test_tier_thresholds_empty():
    t = _compute_tier_thresholds([])
    # anything returns default when no scores
    assert _assign_tier(0.99, t) == "default"

def test_tier_percentile_ordering():
    scores = list(range(100))  # 0–99
    t = _compute_tier_thresholds([float(s) for s in scores])
    # top 5% = score >= 95
    assert _assign_tier(95.0, t) == "elite"
    assert _assign_tier(85.0, t) == "trusted"
    assert _assign_tier(55.0, t) == "solid"
    assert _assign_tier(20.0, t) == "default"

def test_tier_single_score():
    t = _compute_tier_thresholds([0.5])
    # only one score — it's both elite and everything
    assert _assign_tier(0.5, t) == "elite"
