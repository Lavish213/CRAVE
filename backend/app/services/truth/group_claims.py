from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Any

from app.db.models.place_claim import PlaceClaim


def _extract_fingerprint(claim: PlaceClaim) -> str | None:
    """
    Safely extract the fingerprint from a PlaceClaim payload.

    Returns None if the claim is malformed or missing required fields.
    """

    payload = getattr(claim, "value_json", None)

    if not payload:
        return None

    if not isinstance(payload, dict):
        return None

    fingerprint = payload.get("fingerprint")

    if not fingerprint:
        return None

    return str(fingerprint)


def group_menu_claims(
    claims: List[PlaceClaim],
) -> Dict[str, List[PlaceClaim]]:
    """
    Group menu claims by fingerprint.

    Output format:

        {
            fingerprint: [PlaceClaim, PlaceClaim, ...]
        }

    Claims without a valid fingerprint are ignored.
    """

    grouped: Dict[str, List[PlaceClaim]] = defaultdict(list)

    for claim in claims:

        fingerprint = _extract_fingerprint(claim)

        if not fingerprint:
            continue

        grouped[fingerprint].append(claim)

    return grouped