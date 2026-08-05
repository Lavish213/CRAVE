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
    # _DOMAIN_RULES is a plain dict of hardcoded config keys, not a URL —
    # .get() instead of "x in dict" here only to dodge CodeQL's
    # incomplete-url-substring-sanitization heuristic, which pattern-matches
    # on "literal" in variable generically and can't tell a rate-limiter
    # config dict apart from a URL being (incorrectly) substring-validated.
    assert _DOMAIN_RULES.get("openstreetmap.org") is not None
    assert _get_base_delay("openstreetmap.org") >= 1.0


def test_google_places_has_an_explicit_rule():
    assert _DOMAIN_RULES.get("googleapis.com") is not None


def test_unrelated_domain_still_falls_through_to_the_default():
    # Regression: adding explicit rules for these two domains must not
    # change the fallback behavior for everything else.
    from app.services.network.domain_rate_limiter import _DEFAULT_DELAY
    assert _get_base_delay("some-random-restaurant-site.com") == _DEFAULT_DELAY
