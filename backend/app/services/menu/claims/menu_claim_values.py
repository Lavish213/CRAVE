from __future__ import annotations

from typing import Optional, Dict, Any
from datetime import datetime, timezone

from app.services.menu.contracts import (
    MenuClaimPayload,
    NormalizedMenuItem,
)


SCHEMA_VERSION = 1


# =========================================================
# BUILD PAYLOAD
# =========================================================

def build_menu_claim_payload(
    item: NormalizedMenuItem,
    *,
    source_url: Optional[str] = None,
    provider: Optional[str] = None,
    source_type: str = "html",
    external_menu_id: Optional[str] = None,
) -> MenuClaimPayload:

    # 🔥 fallback provider from item
    provider = provider or getattr(item, "provider", None)

    return MenuClaimPayload(
        fingerprint=item.fingerprint,
        name=_clean_str(item.name),
        section=_clean_str(item.section),

        price_cents=item.price_cents,
        currency=_clean_str(item.currency) or "USD",

        description=_clean_str(item.description),
        image_url=_clean_str(getattr(item, "image_url", None)),

        source_url=_clean_str(source_url),

        provider=_clean_str(provider),
        source_type=_clean_str(source_type) or "unknown",

        external_menu_id=_clean_str(external_menu_id),
    )


# =========================================================
# SERIALIZE
# =========================================================

def claim_payload_to_json(payload: MenuClaimPayload) -> Dict[str, Any]:

    return {
        "schema_version": SCHEMA_VERSION,
        "ingested_at": datetime.now(timezone.utc).isoformat(),

        # ---------------- IDENTITY ----------------
        "fingerprint": payload.fingerprint,
        "name": payload.name,
        "section": payload.section,

        # ---------------- PRICING ----------------
        "price_cents": payload.price_cents,
        "currency": payload.currency,

        # ---------------- CONTENT ----------------
        "description": payload.description or None,

        # ---------------- SOURCE ----------------
        "provider": payload.provider,
        "source_type": payload.source_type,
        "external_menu_id": payload.external_menu_id,
        "source_url": payload.source_url,

        # ---------------- IMAGE (🔥 provider/Grubhub item images) ----------------
        "image_url": payload.image_url or None,

        # ---------------- METADATA (🔥 FUTURE SAFE) ----------------
        "metadata": {},
    }


# =========================================================
# HELPERS
# =========================================================

def _clean_str(value: Optional[object]) -> Optional[str]:
    if value is None:
        return None
    try:
        s = str(value).strip()
        return s if s else None
    except Exception:
        return None