from __future__ import annotations

from typing import Any, Dict, Iterable, List

from app.services.menu.contracts import ExtractedMenuItem


DEBUG = False


# =========================================================
# ENTRYPOINT
# =========================================================

def adapt_grubhub_items(items: Iterable[Dict[str, Any]]) -> List[ExtractedMenuItem]:
    out: List[ExtractedMenuItem] = []

    for item in items:
        if not isinstance(item, dict):
            continue

        name = _safe_str(item.get("name") or item.get("item_name"))
        if not name:
            if DEBUG:
                print("ADAPTER_DROP_NO_NAME:", item)
            continue

        try:
            adapted = _adapt_single(item, name)
            out.append(adapted)
        except Exception as exc:
            print("ADAPTER_ERROR:", exc)
            print("ADAPTER_ITEM:", item)
            raise

    return out


# =========================================================
# CORE
# =========================================================

def _adapt_single(item: Dict[str, Any], name: str) -> ExtractedMenuItem:
    name = name.strip()

    section = _safe_str(item.get("provider_category_name")) or "uncategorized"
    price_cents = _extract_price_cents(item)
    min_price_cents = _safe_int(item.get("min_price_cents"))
    max_price_cents = _safe_int(item.get("max_price_cents"))

    currency = (_safe_str(item.get("currency")) or "USD").upper()
    description = _safe_str(item.get("description"))
    image_url = _safe_str(item.get("image_url"))

    provider = _safe_str(item.get("provider")) or "grubhub"
    provider_item_id = _safe_str(item.get("provider_item_id"))

    is_available = item.get("is_available")
    if is_available is not None and not isinstance(is_available, bool):
        is_available = bool(is_available)

    badges = item.get("badges") if isinstance(item.get("badges"), list) else []
    badges = [str(b).strip() for b in badges if str(b).strip()]

    source_type = _safe_str(item.get("source_type")) or "provider"
    source_url = _safe_str(item.get("source_url"))

    modifiers = item.get("modifier_groups") if isinstance(item.get("modifier_groups"), list) else []
    modifiers = [m for m in modifiers if isinstance(m, dict)]

    return ExtractedMenuItem(
        name=name,
        section=section,
        price_cents=price_cents,
        min_price_cents=min_price_cents,
        max_price_cents=max_price_cents,
        currency=currency,
        description=description,
        image_url=image_url,
        provider=provider,
        provider_item_id=provider_item_id,
        is_available=is_available,
        badges=badges,
        source_type=source_type,
        source_url=source_url,
        modifiers=modifiers,
        raw=item,
    )


# =========================================================
# PRICE
# =========================================================

def _extract_price_cents(item: Dict[str, Any]) -> int | None:
    price_cents = _safe_int(item.get("base_price_cents"))

    if price_cents is None:
        price_cents = _safe_int(item.get("min_price_cents"))

    if price_cents is None:
        raw_price = item.get("price")
        try:
            if raw_price is not None:
                price_cents = int(float(str(raw_price)) * 100)
        except Exception:
            price_cents = None

    if price_cents is None:
        return None

    if price_cents < 0:
        return None

    if price_cents > 1_000_000:
        return None

    return price_cents


# =========================================================
# HELPERS
# =========================================================

def _safe_str(value: Any) -> str | None:
    if value is None:
        return None
    try:
        s = str(value).strip()
        return s if s else None
    except Exception:
        return None


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None