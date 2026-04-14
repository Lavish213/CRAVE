# tests/social/test_extractors.py
import pytest
from app.services.social.extractors.tiktok import extract_from_tiktok
from app.services.social.extractors.instagram import extract_from_instagram
from app.services.social.extractors.youtube import extract_from_youtube

# TikTok
def test_tiktok_extracts_handle():
    result = extract_from_tiktok("https://www.tiktok.com/@foodie_la/video/7123456789")
    assert result["creator_handle"] == "foodie_la"
    assert result["confidence"] == 0.40
    assert result["platform"] == "tiktok"

def test_tiktok_no_handle():
    result = extract_from_tiktok("https://vm.tiktok.com/ZMxyz/")
    assert result["creator_handle"] is None
    assert result["confidence"] == 0.0

def test_tiktok_bad_url():
    result = extract_from_tiktok("not a url")
    assert result["platform"] == "tiktok"
    assert result["confidence"] == 0.0

# Instagram
def test_instagram_extracts_handle():
    result = extract_from_instagram("https://www.instagram.com/joespizza/")
    assert result["creator_handle"] == "joespizza"
    assert result["confidence"] == 0.35

def test_instagram_post_no_handle():
    result = extract_from_instagram("https://www.instagram.com/p/CxyzABC/")
    assert result["creator_handle"] is None

# YouTube
def test_youtube_at_handle():
    result = extract_from_youtube("https://www.youtube.com/@FoodChannel")
    assert result["creator_handle"] == "FoodChannel"
    assert result["confidence"] == 0.30

def test_youtube_c_handle():
    result = extract_from_youtube("https://www.youtube.com/c/FoodChannel")
    assert result["creator_handle"] == "FoodChannel"

def test_youtube_no_handle():
    result = extract_from_youtube("https://www.youtube.com/watch?v=abc123")
    assert result["creator_handle"] is None
    assert result["confidence"] == 0.0

# All return correct contract keys
@pytest.mark.parametrize("fn,url", [
    (extract_from_tiktok, "https://tiktok.com/@x"),
    (extract_from_instagram, "https://instagram.com/x"),
    (extract_from_youtube, "https://youtube.com/@x"),
])
def test_extractor_contract(fn, url):
    result = fn(url)
    for key in ("platform", "creator_handle", "confidence", "source_url", "place_name_hint"):
        assert key in result
