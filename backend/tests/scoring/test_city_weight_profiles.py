# tests/scoring/test_city_weight_profiles.py
import pytest
from app.services.scoring.city_weight_profiles import get_profile, DEFAULT_PROFILE, SIGNALS

def test_default_profile_sums_to_one():
    total = sum(DEFAULT_PROFILE.values())
    assert abs(total - 1.0) < 0.001

def test_default_profile_has_all_signals():
    for signal in SIGNALS:
        assert signal in DEFAULT_PROFILE, f"Missing signal: {signal}"

def test_get_profile_returns_default_for_unknown_city():
    profile = get_profile("atlantis")
    assert profile is DEFAULT_PROFILE

def test_get_profile_returns_default_for_none():
    profile = get_profile(None)
    assert profile is DEFAULT_PROFILE

def test_nyc_profile_sums_to_one():
    profile = get_profile("nyc")
    assert abs(sum(profile.values()) - 1.0) < 0.001

def test_nyc_awards_heavier_than_default():
    nyc = get_profile("nyc")
    assert nyc["awards_score"] > DEFAULT_PROFILE["awards_score"]

def test_la_creator_heavier_than_default():
    la = get_profile("los_angeles")
    assert la["creator_score"] > DEFAULT_PROFILE["creator_score"]

def test_all_city_profiles_sum_to_one():
    from app.services.scoring.city_weight_profiles import CITY_PROFILES
    for slug, profile in CITY_PROFILES.items():
        total = sum(profile.values())
        assert abs(total - 1.0) < 0.001, f"{slug} profile sums to {total}"
