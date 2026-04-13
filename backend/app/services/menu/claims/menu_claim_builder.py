from __future__ import annotations

import logging
from typing import List, Optional, Set

from sqlalchemy.orm import Session

from app.db.models.menu_item import MenuItem
from app.services.menu.contracts import NormalizedMenuItem


logger = logging.getLogger(__name__)


MAX_ITEMS = 2000


# ---------------------------------------------------------
# BUILD (NO DB SIDE EFFECTS)
# ---------------------------------------------------------

def build_menu_items(
    *,
    place_id: str,
    items: List[NormalizedMenuItem],
) -> List[MenuItem]:

    if not place_id or not items:
        return []

    built: List[MenuItem] = []
    seen: Set[str] = set()

    for item in items:

        try:
            name = _clean(item.name)
            if not name:
                continue

            section = _clean(item.section)
            description = _clean(getattr(item, "description", None))
            currency = _clean(item.currency)

            # ---------------- PRICE ----------------
            price_cents = _safe_int(getattr(item, "price_cents", None))
            price = price_cents / 100 if price_cents is not None else None

            # ---------------- FINGERPRINT (🔥 FIXED) ----------------
            fingerprint = item.fingerprint

            if not fingerprint:
                logger.debug("missing_fingerprint_skip name=%s", name)
                continue

            fingerprint = fingerprint.strip().lower()

            # ---------------- DEDUPE ----------------
            if fingerprint in seen:
                continue

            seen.add(fingerprint)

            built.append(
                MenuItem(
                    place_id=place_id,
                    name=name,
                    section=section,
                    description=description,
                    price=price,
                    currency=currency,
                    fingerprint=fingerprint,
                )
            )

            if len(built) >= MAX_ITEMS:
                break

        except Exception as exc:
            logger.debug("menu_item_build_failed error=%s", exc)

    return built


# ---------------------------------------------------------
# UPSERT (PRIMARY)
# ---------------------------------------------------------

def upsert_menu_items(
    *,
    db: Session,
    place_id: str,
    items: List[NormalizedMenuItem],
) -> int:

    if not place_id or not items:
        return 0

    try:

        built = build_menu_items(
            place_id=place_id,
            items=items,
        )

        if not built:
            return 0

        existing = db.query(MenuItem.fingerprint).filter(
            MenuItem.place_id == place_id
        ).all()

        existing_set = {row[0] for row in existing}

        to_insert = [
            item for item in built
            if item.fingerprint not in existing_set
        ]

        if not to_insert:
            return 0

        db.bulk_save_objects(to_insert)
        db.commit()

        logger.info(
            "menu_items_upsert_success place_id=%s inserted=%s total=%s",
            place_id,
            len(to_insert),
            len(built),
        )

        return len(to_insert)

    except Exception as exc:
        db.rollback()
        logger.exception(
            "menu_items_upsert_failed place_id=%s error=%s",
            place_id,
            exc,
        )
        return 0


# ---------------------------------------------------------
# FULL REPLACE (CONTROLLED)
# ---------------------------------------------------------

def replace_menu_items(
    *,
    db: Session,
    place_id: str,
    items: List[NormalizedMenuItem],
) -> int:

    if not place_id:
        return 0

    try:

        db.query(MenuItem).filter(
            MenuItem.place_id == place_id
        ).delete()

        built = build_menu_items(
            place_id=place_id,
            items=items,
        )

        if not built:
            db.commit()
            return 0

        db.bulk_save_objects(built)
        db.commit()

        logger.info(
            "menu_items_replace_success place_id=%s items=%s",
            place_id,
            len(built),
        )

        return len(built)

    except Exception as exc:
        db.rollback()
        logger.exception(
            "menu_items_replace_failed place_id=%s error=%s",
            place_id,
            exc,
        )
        return 0


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    try:
        v = str(value).strip()
        return v or None
    except Exception:
        return None


def _safe_int(value) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None