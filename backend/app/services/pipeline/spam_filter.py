from __future__ import annotations

import re
from app.services.pipeline.candidate_normalizer import NormalizedCandidate

MIN_CONFIDENCE = 0.30
MIN_NAME_LEN = 3

_SPAM_HANDLES = frozenset({
    "foodie", "eater", "mukbang", "asmr", "challenge", "prank",
    "viral", "trending", "fyp", "foryou", "foryoupage",
})

_SPAM_URL_PATTERNS = [
    re.compile(r"bit\.ly/"),
    re.compile(r"tinyurl\.com/"),
    re.compile(r"utm_source"),
]


def is_spam(candidate: NormalizedCandidate) -> tuple[bool, str]:
    """
    Returns (is_spam, reason).
    """
    if candidate.confidence < MIN_CONFIDENCE:
        return True, f"confidence_too_low ({candidate.confidence:.2f})"

    if len(candidate.name) < MIN_NAME_LEN:
        return True, "name_too_short"

    name_lower = candidate.name.lower()
    if any(h in name_lower for h in _SPAM_HANDLES):
        return True, "spam_handle_in_name"

    if candidate.source_url:
        for pattern in _SPAM_URL_PATTERNS:
            if pattern.search(candidate.source_url):
                return True, "spam_url_pattern"

    return False, ""


def filter_candidates(
    candidates: list[NormalizedCandidate],
) -> tuple[list[NormalizedCandidate], list[tuple[NormalizedCandidate, str]]]:
    """
    Returns (accepted, rejected_with_reason).
    """
    accepted = []
    rejected = []
    for c in candidates:
        spam, reason = is_spam(c)
        if spam:
            rejected.append((c, reason))
        else:
            accepted.append(c)
    return accepted, rejected
