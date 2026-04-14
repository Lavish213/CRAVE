# tests/social/test_caption_parser.py
import pytest
from app.services.social.caption_parser import parse_caption

def test_empty_text_returns_empty():
    result = parse_caption("")
    assert result.hashtags == []
    assert result.place_candidates == []

def test_extracts_hashtags():
    result = parse_caption("Great food! #foodie #bayarea #eats")
    assert "foodie" in result.hashtags
    assert "bayarea" in result.hashtags

def test_extracts_location_line():
    result = parse_caption("📍 Joe's Tacos\nSo good!")
    assert "Joe's Tacos" in result.location_lines
    assert "Joe's Tacos" in result.place_candidates

def test_extracts_at_pattern():
    result = parse_caption("Had the best burger at Joe's Diner last night")
    assert any("Joe" in c for c in result.place_candidates)

def test_extracts_geo_hints_city_state():
    result = parse_caption("Best pizza in Oakland, CA!")
    assert any("Oakland" in h for h in result.geo_hints)

def test_has_food_terms():
    result = parse_caption("This restaurant has the best menu")
    assert result.has_food_terms is True

def test_no_food_terms():
    result = parse_caption("Look at this cool car show")
    assert result.has_food_terms is False

def test_none_input():
    result = parse_caption(None)
    assert result.hashtags == []

def test_to_dict_has_all_keys():
    result = parse_caption("test").to_dict()
    for key in ("hashtags", "mentions", "location_lines", "place_candidates", "geo_hints", "has_food_terms"):
        assert key in result
