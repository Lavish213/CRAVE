from __future__ import annotations




# ---------------------------------------------------------
# BRAND ALIASES
# ---------------------------------------------------------

BRAND_ALIASES = {
    "mcdonalds": ["mcdonald's", "mc donalds", "mcdonald"],
    "burger king": ["burgerking"],
    "taco bell": ["tacobell"],
    "kfc": ["kentucky fried chicken"],
}


# ---------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------

def resolve_brand_alias(name: str | None) -> str | None:
    """
    Normalize known brand aliases to canonical name.

    Example:
    "mcdonald's" → "mcdonalds"
    """

    if not name:
        return None

    name = name.lower().strip()

    for canonical, aliases in BRAND_ALIASES.items():

        if name == canonical:
            return canonical

        if name in aliases:
            return canonical

    return name