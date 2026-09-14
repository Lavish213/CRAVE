"""
Coverage for feed_ranker._chain_penalty's name-matching rule.

Previously a raw substring check (`if chain in name`), which could dock an
unrelated local business whose name happens to contain a chain's name as
one word among others -- e.g. "La Panera Bakery" is not Panera Bread, "Sonic
Drive-In Tacos of Fresno" is not Sonic. Fixed to match only when the
place's normalized name starts with a known chain marker, which still
catches real chain locations (chain name is always the leading words, plus
an optional store number/suffix) while dropping that false-positive class.
These are pure in-memory Place constructions -- no DB required, since
_chain_penalty only reads `p.name`.
"""
from __future__ import annotations

from app.db.models.place import Place
from app.services.feed.feed_ranker import _CHAIN_PENALTY, _chain_penalty


def _place(name: str) -> Place:
    return Place(name=name, city_id="test-city")


def test_exact_chain_name_is_penalized():
    assert _chain_penalty(_place("McDonald's")) == _CHAIN_PENALTY


def test_chain_name_with_store_suffix_is_penalized():
    assert _chain_penalty(_place("Panera Bread - Downtown")) == _CHAIN_PENALTY
    assert _chain_penalty(_place("Starbucks #4521")) == _CHAIN_PENALTY


def test_unrelated_local_business_containing_chain_word_is_not_penalized():
    """The real bug this fix closes: a chain's name appearing as one word
    inside an unrelated business's own name must not be docked."""
    assert _chain_penalty(_place("La Panera Bakery")) == 0.0
    assert _chain_penalty(_place("Downtown Subway Station Cafe")) == 0.0


def test_plain_local_restaurant_is_not_penalized():
    assert _chain_penalty(_place("Horn Barbecue")) == 0.0
    assert _chain_penalty(_place("Mama Lupe's Kitchen")) == 0.0
