"""
Coverage for app.services.network.domain_rate_limiter — specifically that
Nominatim and Google Places have EXPLICIT per-domain rules (added during a
full-app audit) rather than silently relying on _DEFAULT_DELAY. Before this,
both domains fell through to the generic default and happened to satisfy
Nominatim's 1 req/sec usage policy only by accident.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.network.domain_rate_limiter import _DOMAIN_RULES, _get_base_delay


def test_nominatim_has_an_explicit_rule_satisfying_its_1_req_per_sec_policy():
    assert "openstreetmap.org" in _DOMAIN_RULES
    assert _get_base_delay("openstreetmap.org") >= 1.0


def test_google_places_has_an_explicit_rule():
    assert "googleapis.com" in _DOMAIN_RULES


def test_unrelated_domain_still_falls_through_to_the_default():
    # Regression: adding explicit rules for these two domains must not
    # change the fallback behavior for everything else.
    from app.services.network.domain_rate_limiter import _DEFAULT_DELAY
    assert _get_base_delay("some-random-restaurant-site.com") == _DEFAULT_DELAY
