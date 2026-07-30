# tests/scoring/test_signal_context.py
#
# Was tests/scoring/test_place_score_v3.py — despite the old filename, most
# of it tested SignalContext (live: imported by app/workers/
# recompute_scores_worker.py, the real v4 scoring path the scheduler calls).
# The compute_place_score_v3/_redistribute_weights tests that used to follow
# were removed along with app/services/scoring/place_score_v3.py itself,
# confirmed dead: zero importers anywhere outside this test file, and
# place_score_v4.py's own header comment says "DO NOT import place_score_v3;
# helpers are copied here intentionally."
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
