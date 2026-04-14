# tests/scoring/test_place_score_v3.py
import pytest
from app.services.scoring.signal_context import SignalContext

def test_signal_context_defaults():
    ctx = SignalContext()
    assert ctx.image_count("unknown-id") == 0
    assert ctx.menu_item_count("unknown-id") == 0
    assert ctx.has_primary_image("unknown-id") is False
    assert ctx.hitlist_score("unknown-id") == 0.0

def test_signal_context_lookup():
    ctx = SignalContext(
        image_counts={"place-1": 5},
        menu_item_counts={"place-1": 30},
        has_primary={"place-1"},
        hitlist_scores={"place-1": 0.75},
    )
    assert ctx.image_count("place-1") == 5
    assert ctx.menu_item_count("place-1") == 30
    assert ctx.has_primary_image("place-1") is True
    assert ctx.hitlist_score("place-1") == 0.75
    # missing place returns safe defaults
    assert ctx.image_count("place-2") == 0
    assert ctx.has_primary_image("place-2") is False

from datetime import datetime, timezone, timedelta
from app.services.scoring.place_score_v3 import compute_place_score_v3, _redistribute_weights

def _make_score(
    place_id="abc-123-def-456",
    name="",
    lat=None, lng=None,
    has_menu=False, website=None,
    updated_at=None,
    grubhub_url=None, menu_source_url=None,
    image_count=0, has_primary_image=False,
    menu_item_count=0,
    city_slug=None,
):
    return compute_place_score_v3(
        place_id=place_id, name=name, lat=lat, lng=lng,
        has_menu=has_menu, website=website, updated_at=updated_at,
        grubhub_url=grubhub_url, menu_source_url=menu_source_url,
        image_count=image_count, has_primary_image=has_primary_image,
        menu_item_count=menu_item_count, city_slug=city_slug,
    )

def test_empty_place_scores_low():
    result = _make_score()
    assert result.final_score < 0.15

def test_rich_place_scores_higher_than_empty():
    empty = _make_score()
    rich = _make_score(
        has_menu=True, image_count=8, has_primary_image=True,
        menu_item_count=40, grubhub_url="https://grubhub.com/foo",
        updated_at=datetime.now(timezone.utc),
    )
    assert rich.final_score > empty.final_score

def test_score_bounded_0_to_1():
    result = _make_score(
        has_menu=True, image_count=20, has_primary_image=True,
        menu_item_count=100, grubhub_url="https://grubhub.com/foo",
        updated_at=datetime.now(timezone.utc),
    )
    assert 0.0 <= result.final_score <= 1.0

def test_recency_fresh_place():
    now = datetime.now(timezone.utc)
    result = _make_score(updated_at=now)
    assert result.signals["recency_score"] == 1.0

def test_recency_stale_place():
    old = datetime.now(timezone.utc) - timedelta(days=91)
    result = _make_score(updated_at=old)
    assert result.signals["recency_score"] == 0.0

def test_menu_score_normalized():
    result = _make_score(menu_item_count=25)
    assert result.signals["menu_score"] == 0.5

    result_capped = _make_score(menu_item_count=100)
    assert result_capped.signals["menu_score"] == 1.0

def test_image_score_normalized():
    result = _make_score(image_count=5)
    assert result.signals["image_score"] == 0.5

def test_completeness_full():
    result = _make_score(
        name="Joe's Diner", lat=37.7, lng=-122.4,
        has_primary_image=True, has_menu=True,
    )
    assert result.signals["completeness_score"] == 1.0

def test_completeness_empty():
    result = _make_score(name="", lat=None, lng=None,
                         has_primary_image=False, has_menu=False)
    assert result.signals["completeness_score"] == 0.0

def test_deterministic_same_input():
    r1 = _make_score(has_menu=True, image_count=3)
    r2 = _make_score(has_menu=True, image_count=3)
    assert r1.final_score == r2.final_score

def test_uuid_entropy_tiebreak_is_tiny():
    r = _make_score()
    assert r.final_score < 0.000002  # entropy only

def test_redistribute_weights_all_zero():
    weights = {"a": 0.6, "b": 0.4}
    signals = {"a": 0.0, "b": 0.0}
    result = _redistribute_weights(weights, signals)
    # nothing to redistribute to — return original
    assert result == weights

def test_redistribute_weights_one_missing():
    weights = {"a": 0.5, "b": 0.5}
    signals = {"a": 1.0, "b": 0.0}
    result = _redistribute_weights(weights, signals)
    assert abs(result["a"] - 1.0) < 0.001
    assert result["b"] == 0.0
