from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SearchInterpretation:
    original_query: str
    lookup_query: str
    price_tier: int | None = None
    required_categories: tuple[str, ...] = ()
    hard_constraints: tuple[str, ...] = ()
    unsupported_hard_constraints: tuple[str, ...] = ()
    context: tuple[str, ...] = ()
    uncertain: bool = False


_PHRASES: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"\bnear\s+me\b", re.I), "context", "near_me"),
    (re.compile(r"\bdate\s+night\b", re.I), "context", "date_night"),
    (re.compile(r"\bopen\s+late\b", re.I), "context", "open_late"),
    (re.compile(r"\bquick\s+(?:bite|lunch|dinner)\b", re.I), "context", "quick"),
    (re.compile(r"\b(?:cheap|budget|inexpensive)\b", re.I), "price", "1"),
    (re.compile(r"\b(?:splurge|expensive|fine\s+dining)\b", re.I), "price", "4"),
    (re.compile(r"\bvegan\b", re.I), "category", "Vegan"),
    (re.compile(r"\bvegetarian\b", re.I), "category", "Vegetarian"),
    (re.compile(r"\bhalal\b", re.I), "category", "Halal"),
    (re.compile(r"\bkosher\b", re.I), "category", "Kosher"),
    (re.compile(r"\bgluten[-\s]?free\b", re.I), "category", "Gluten Free"),
)

_UNSUPPORTED_HARD: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(?:nut|peanut|tree[-\s]?nut)[-\s]?free\b", re.I), "nut_free"),
    (re.compile(r"\ballergy[-\s]?safe\b", re.I), "allergy_safe"),
)

_FOOD_FILLERS = re.compile(r"\b(?:food|restaurant|restaurants|place|places)\b", re.I)


def _clean_query(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" ,.-")


def interpret_search_query(query: str) -> SearchInterpretation:
    """Deterministically separate lookup text from supported context.

    This is deliberately conservative. It never claims an allergy can be
    enforced from catalog data that does not prove it, and it leaves unknown
    wording intact for ordinary lookup instead of asking an LLM to invent
    semantics.
    """
    original = _clean_query(query)
    remaining = original
    price_tier: int | None = None
    categories: list[str] = []
    contexts: list[str] = []
    hard: list[str] = []
    unsupported: list[str] = []

    for pattern, key in _UNSUPPORTED_HARD:
        if pattern.search(remaining):
            hard.append(key)
            unsupported.append(key)
            remaining = pattern.sub(" ", remaining)

    matched_phrases = []
    for pattern, kind, value in _PHRASES:
        match = pattern.search(remaining)
        if match:
            matched_phrases.append((match.start(), pattern, kind, value))

    for _, pattern, kind, value in sorted(matched_phrases, key=lambda item: item[0]):
        remaining = pattern.sub(" ", remaining)
        if kind == "price":
            price_tier = int(value)
        elif kind == "category":
            categories.append(value)
            hard.append(value.lower().replace(" ", "_"))
        else:
            contexts.append(value)

    lookup = _clean_query(remaining)
    if not lookup:
        lookup = "restaurant"

    # Context-only searches need a broad fallback and an honest uncertainty
    # marker because occasion/open-now semantics are not yet fully indexed.
    meaningful = _clean_query(_FOOD_FILLERS.sub(" ", lookup))
    # Occasion/time language is surfaced to the user but is not yet backed by
    # reliable catalog fields. Mark it uncertain instead of pretending it was
    # enforced. `near_me` is handled by request coordinates in the route.
    unenforced_contexts = {"date_night", "open_late", "quick"}
    uncertain = (
        bool(unsupported)
        or bool(unenforced_contexts.intersection(contexts))
        or (not meaningful and bool(contexts))
    )

    return SearchInterpretation(
        original_query=original,
        lookup_query=lookup,
        price_tier=price_tier,
        required_categories=tuple(dict.fromkeys(categories)),
        hard_constraints=tuple(dict.fromkeys(hard)),
        unsupported_hard_constraints=tuple(dict.fromkeys(unsupported)),
        context=tuple(dict.fromkeys(contexts)),
        uncertain=uncertain,
    )
