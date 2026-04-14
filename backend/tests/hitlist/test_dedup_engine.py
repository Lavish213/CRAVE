# tests/hitlist/test_dedup_engine.py
import pytest
from app.services.hitlist.dedup_engine import compute_dedup_key

def test_place_id_takes_priority():
    key = compute_dedup_key(place_id="abc-123", source_url="https://tiktok.com/x", place_name="Joe's")
    assert key.startswith("place:")
    assert "abc-123" in key

def test_source_url_second():
    key = compute_dedup_key(source_url="https://tiktok.com/@user/video/123", place_name="Joe's")
    assert key.startswith("url:")

def test_geo_third():
    key = compute_dedup_key(place_name="Joe's Tacos", lat=37.7749, lng=-122.4194)
    assert key.startswith("geo:")

def test_city_fourth():
    key = compute_dedup_key(place_name="Joe's Tacos", city="Oakland")
    assert key.startswith("city:")

def test_name_only_fallback():
    key = compute_dedup_key(place_name="Joe's Tacos")
    assert key.startswith("name:")

def test_no_data_raises():
    with pytest.raises(ValueError):
        compute_dedup_key()

def test_same_inputs_produce_same_key():
    k1 = compute_dedup_key(place_name="Joe's Tacos", city="Oakland")
    k2 = compute_dedup_key(place_name="Joe's Tacos", city="Oakland")
    assert k1 == k2

def test_different_names_produce_different_keys():
    k1 = compute_dedup_key(place_name="Joe's Tacos", city="Oakland")
    k2 = compute_dedup_key(place_name="Maria's Tacos", city="Oakland")
    assert k1 != k2

def test_case_insensitive_name():
    k1 = compute_dedup_key(place_name="JOE'S TACOS", city="Oakland")
    k2 = compute_dedup_key(place_name="joe's tacos", city="Oakland")
    assert k1 == k2

def test_geo_rounding():
    # Slight coord difference within 4dp rounds to same key
    k1 = compute_dedup_key(place_name="Test", lat=37.77491, lng=-122.41941)
    k2 = compute_dedup_key(place_name="Test", lat=37.77499, lng=-122.41949)
    assert k1 == k2
