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

from app.services.query.map_query import _assign_tier

def test_tier_uses_stable_city_percentile_bands():
    assert _assign_tier(0.01, 0.95) == "elite"
    assert _assign_tier(0.99, 0.85) == "trusted"
    assert _assign_tier(0.99, 0.55) == "solid"
    assert _assign_tier(0.99, 0.20) == "default"


def test_tier_falls_back_to_app_wide_absolute_score_bands():
    assert _assign_tier(0.42, None) == "elite"
    assert _assign_tier(0.32, None) == "trusted"
    assert _assign_tier(0.22, None) == "solid"
    assert _assign_tier(0.21, None) == "default"
