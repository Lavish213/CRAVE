# tests/hitlist/test_aggregator.py
import pytest
from datetime import datetime, timezone, timedelta
from app.services.hitlist.aggregator import aggregate_saves

def _save(name, city, hours_ago=0):
    return {
        "place_name": name,
        "city": city,
        "timestamp": datetime.now(timezone.utc) - timedelta(hours=hours_ago),
    }

def test_empty_input():
    assert aggregate_saves([]) == []

def test_single_save():
    result = aggregate_saves([_save("Joe's", "Oakland", 0)])
    assert len(result) == 1
    assert result[0]["save_count"] == 1
    assert result[0]["recent_velocity"] == 1

def test_recent_saves_score_higher():
    recent = [_save("Hot Spot", "SF", hours_ago=1)] * 10
    old = [_save("Old Spot", "SF", hours_ago=25)] * 10
    result = aggregate_saves(recent + old)
    scores = {r["place_name"]: r["score"] for r in result}
    assert scores["Hot Spot"] > scores["Old Spot"]

def test_sorted_by_score_descending():
    saves = (
        [_save("Hot", "SF", 1)] * 10 +
        [_save("Medium", "SF", 1)] * 5 +
        [_save("Cold", "SF", 25)] * 10
    )
    result = aggregate_saves(saves)
    scores = [r["score"] for r in result]
    assert scores == sorted(scores, reverse=True)

def test_score_bounded_0_1():
    saves = [_save("Test", "SF", 0)] * 200
    result = aggregate_saves(saves)
    assert 0.0 <= result[0]["score"] <= 1.0
