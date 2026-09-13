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
    # Amenity requirements (outdoor seating, ...) -- deliberately a separate
    # field from required_categories/hard_constraints, not folded into
    # either: those two are documented elsewhere (see SearchScreen.tsx) as
    # always meaning "the dietary/allergy phrases," and callers rely on
    # that invariant. An amenity is enforced with the same never-silently-
    # relaxed standing as a dietary hard constraint, just filtered against
    # a plain Place column (outdoor_seating) rather than a category join.
    required_amenities: tuple[str, ...] = ()
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
    (re.compile(r"\b(?:patio|outdoor\s+seating)\b", re.I), "amenity", "outdoor_seating"),
)

_UNSUPPORTED_HARD: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(?:nut|peanut|tree[-\s]?nut)[-\s]?free\b", re.I), "nut_free"),
    (re.compile(r"\ballergy[-\s]?safe\b", re.I), "allergy_safe"),
)

_FOOD_FILLERS = re.compile(r"\b(?:food|restaurant|restaurants|place|places)\b", re.I)
_NEGATION_PREFIX = re.compile(r"(?:\bnon[-\s]?|\bnot\s+)$", re.I)
# Amenities are far more often negated with a plain "no" ("no outdoor
# seating") than dietary categories are -- extending the dietary check
# itself to "no X" risks false-inverting "no [cuisine/dish]" phrasing this
# wasn't scoped to re-audit, so amenities get their own, wider prefix
# instead of touching the shared one above.
_AMENITY_NEGATION_PREFIX = re.compile(r"(?:\bnon[-\s]?|\bnot\s+|\bno\s+)$", re.I)


def _clean_query(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" ,.-")


def _is_negated(text: str, match: re.Match[str], prefix_pattern: re.Pattern[str] = _NEGATION_PREFIX) -> bool:
    """Return True when a supported category/amenity term is explicitly negated.

    Category/amenity extraction is a hard-filter operation. Treating
    `non-vegan`/`not vegan` (or `no outdoor seating`) as positive evidence
    would invert the user's request, so negated terms remain in lookup text
    and make the interpretation uncertain instead of being converted into a
    positive constraint.
    """
    prefix = text[max(0, match.start() - 8):match.start()]
    return bool(prefix_pattern.search(prefix))


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
    amenities: list[str] = []
    hard: list[str] = []
    unsupported: list[str] = []
    negated_category = False

    for pattern, key in _UNSUPPORTED_HARD:
        if pattern.search(remaining):
            hard.append(key)
            unsupported.append(key)
            remaining = pattern.sub(" ", remaining)

    matched_phrases = []
    for pattern, kind, value in _PHRASES:
        match = pattern.search(remaining)
        if match:
            if kind == "category" and _is_negated(remaining, match):
                negated_category = True
                continue
            if kind == "amenity" and _is_negated(remaining, match, _AMENITY_NEGATION_PREFIX):
                negated_category = True
                continue
            matched_phrases.append((match.start(), pattern, kind, value))

    for _, pattern, kind, value in sorted(matched_phrases, key=lambda item: item[0]):
        remaining = pattern.sub(" ", remaining)
        if kind == "price":
            price_tier = int(value)
        elif kind == "category":
            categories.append(value)
            hard.append(value.lower().replace(" ", "_"))
        elif kind == "amenity":
            amenities.append(value)
        else:
            contexts.append(value)

    lookup = _clean_query(remaining)
    if not lookup:
        lookup = "restaurant"

    meaningful = _clean_query(_FOOD_FILLERS.sub(" ", lookup))
    unenforced_contexts = {"date_night", "open_late", "quick"}
    uncertain = (
        bool(unsupported)
        or negated_category
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
        required_amenities=tuple(dict.fromkeys(amenities)),
        uncertain=uncertain,
    )
