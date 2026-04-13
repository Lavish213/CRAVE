from __future__ import annotations

import hashlib
from typing import Any, Optional


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _generate_claim_key(field: str, value: Any) -> str:
    raw = f"{field}:{str(value)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def normalize_claim(
    *,
    field: str,
    value: Any,
    source: str,
    confidence: float | None = None,
    weight: float | None = None,
    provider: str | None = None,
    external_id: str | None = None,
    source_url: str | None = None,
    is_user_submitted: bool = False,
    is_verified_source: bool = False,
    raw: dict | None = None,
) -> dict:
    """
    Converts arbitrary claim input into canonical PlaceClaim schema.
    """

    if not field:
        raise ValueError("Claim field cannot be empty.")

    value_text = None
    value_number = None
    value_json = None

    if isinstance(value, (int, float)):
        value_number = float(value)
    elif isinstance(value, dict):
        value_json = value
    else:
        value_text = _normalize_text(str(value))

    claim_key = _generate_claim_key(field, value)

    return {
        "field": field.strip(),
        "value_text": value_text,
        "value_number": value_number,
        "value_json": value_json,
        "source": source.strip(),
        "confidence": float(confidence) if confidence is not None else 0.5,
        "weight": float(weight) if weight is not None else 1.0,
        "provider": provider,
        "external_id": external_id,
        "source_url": source_url,
        "claim_key": claim_key,
        "is_user_submitted": is_user_submitted,
        "is_verified_source": is_verified_source,
        "raw": raw,
    }