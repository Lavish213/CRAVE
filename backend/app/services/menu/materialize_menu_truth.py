from __future__ import annotations

import hashlib
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.db.models.place_claim import PlaceClaim
from app.db.models.place_truth import PlaceTruth
from app.services.menu.contracts import (
    CanonicalMenu,
    CanonicalMenuItem,
    CanonicalMenuSection,
)
from app.services.truth.group_claims import group_menu_claims
from app.services.truth.score_candidates import score_candidate_group


logger = logging.getLogger(__name__)


TRUTH_TYPE = "menu"
SCHEMA_VERSION = 3
MIN_TRUTH_ITEMS = 2
DEFAULT_SECTION = "Other"
DEFAULT_CURRENCY = "USD"


# =========================================================
# SAFE HELPERS
# =========================================================

def _safe_str(val: object) -> Optional[str]:
    try:
        if val is None:
            return None
        v = str(val).strip()
        return v or None
    except Exception:
        return None


def _safe_int(val: object) -> Optional[int]:
    try:
        if val is None or val == "":
            return None
        return int(val)
    except Exception:
        return None


def _safe_float(val: object, default: float = 0.0) -> float:
    try:
        if val is None or val == "":
            return default
        return float(val)
    except Exception:
        return default


# =========================================================
# CLAIM EXTRACTION
# =========================================================

def _extract_payload(claim: PlaceClaim) -> dict:
    value_json = getattr(claim, "value_json", None)
    return value_json if isinstance(value_json, dict) else {}


def _extract_fingerprint(claim: PlaceClaim, payload: dict) -> Optional[str]:
    return (
        _safe_str(payload.get("fingerprint"))
        or _safe_str(getattr(claim, "claim_key", None))
    )


def _extract_confidence(value: object) -> float:
    return _safe_float(value, 0.0)


# =========================================================
# BUILD ITEMS
# =========================================================

def _build_menu_items(
    grouped_claims: Dict[str, List[PlaceClaim]],
) -> List[CanonicalMenuItem]:

    items: List[CanonicalMenuItem] = []

    for group_key, claims in grouped_claims.items():

        if not claims:
            continue

        try:
            winner, confidence = score_candidate_group(claims)
        except Exception as exc:
            logger.debug("score_failed group=%s error=%s", group_key, exc)
            continue

        payload = _extract_payload(winner)

        name = _safe_str(payload.get("name"))
        fingerprint = _extract_fingerprint(winner, payload)

        if not name or not fingerprint:
            continue

        items.append(
            CanonicalMenuItem(
                name=name,
                section=_safe_str(payload.get("section")) or DEFAULT_SECTION,
                price_cents=_safe_int(payload.get("price_cents")),
                currency=_safe_str(payload.get("currency")) or DEFAULT_CURRENCY,
                description=_safe_str(payload.get("description")),
                confidence_score=_extract_confidence(confidence),
                fingerprint=fingerprint,
            )
        )

    return items


# =========================================================
# GROUP SECTIONS
# =========================================================

def _group_sections(items: List[CanonicalMenuItem]) -> List[CanonicalMenuSection]:

    section_map: Dict[str, List[CanonicalMenuItem]] = defaultdict(list)

    for item in items:
        section_map[
            _safe_str(getattr(item, "section", None)) or DEFAULT_SECTION
        ].append(item)

    sections: List[CanonicalMenuSection] = []

    for section_name in sorted(section_map.keys(), key=lambda x: x.lower()):

        section_items = section_map[section_name]

        section_items.sort(
            key=lambda item: (
                (item.name or "").lower(),
                item.price_cents if item.price_cents is not None else 10**12,
                item.fingerprint or "",
            )
        )

        sections.append(
            CanonicalMenuSection(
                name=section_name,
                items=section_items,
            )
        )

    return sections


# =========================================================
# BUILD MENU
# =========================================================

def build_canonical_menu(claims: List[PlaceClaim]) -> CanonicalMenu:

    if not claims:
        return CanonicalMenu(sections=[], item_count=0)

    grouped = group_menu_claims(claims)
    items = _build_menu_items(grouped)

    if not items:
        return CanonicalMenu(sections=[], item_count=0)

    return CanonicalMenu(
        sections=_group_sections(items),
        item_count=len(items),
    )


# =========================================================
# HASH
# =========================================================

def _menu_hash(menu: CanonicalMenu) -> str:

    flat: List[Tuple] = []

    for section in menu.sections:
        for item in section.items:
            flat.append(
                (
                    (item.name or "").lower(),
                    item.price_cents,
                    (item.currency or DEFAULT_CURRENCY).upper(),
                    (item.description or "").lower(),
                    item.fingerprint,
                )
            )

    flat.sort()

    raw = json.dumps(flat, separators=(",", ":"), ensure_ascii=False)

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# =========================================================
# CHANGE DETECTION
# =========================================================

def _detect_changes(old_menu: Optional[dict], new_menu: CanonicalMenu) -> dict:

    if not isinstance(old_menu, dict):
        return {"added": new_menu.item_count, "removed": 0, "price_changed": 0}

    old_items = {}
    new_items = {}

    for section in old_menu.get("sections", []) or []:
        section_name = _safe_str(section.get("name")) or DEFAULT_SECTION

        for item in section.get("items", []) or []:
            key = (
                (_safe_str(item.get("name")) or "").lower(),
                section_name.lower(),
                (_safe_str(item.get("fingerprint")) or "").lower(),
            )
            old_items[key] = item

    added = removed = price_changed = 0

    for section in new_menu.sections:
        section_name = (_safe_str(section.name) or DEFAULT_SECTION).lower()

        for item in section.items:
            key = (
                (item.name or "").lower(),
                section_name,
                (item.fingerprint or "").lower(),
            )

            new_items[key] = item

            if key not in old_items:
                added += 1
            elif _safe_int(old_items[key].get("price_cents")) != item.price_cents:
                price_changed += 1

    for key in old_items:
        if key not in new_items:
            removed += 1

    return {
        "added": added,
        "removed": removed,
        "price_changed": price_changed,
    }


# =========================================================
# SERIALIZE
# =========================================================

def _serialize_menu(menu: CanonicalMenu, previous_menu: Optional[dict]) -> dict:

    return {
        "schema_version": SCHEMA_VERSION,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "menu_hash": _menu_hash(menu),
        "changes": _detect_changes(previous_menu, menu),
        "sections": [
            {
                "name": section.name,
                "items": [
                    {
                        "name": item.name,
                        "section": section.name,
                        "price_cents": item.price_cents,
                        "currency": item.currency or DEFAULT_CURRENCY,
                        "description": item.description,
                        "confidence_score": item.confidence_score,
                        "fingerprint": item.fingerprint,
                    }
                    for item in section.items
                ],
            }
            for section in menu.sections
        ],
        "metadata": {
            "section_count": len(menu.sections),
            "item_count": menu.item_count,
        },
    }


# =========================================================
# MAIN MATERIALIZER
# =========================================================

def materialize_menu_truth(
    *,
    db: Session,
    place_id: str,
) -> Optional[CanonicalMenu]:

    try:
        claims = (
            db.query(PlaceClaim)
            .filter(
                PlaceClaim.place_id == place_id,
                PlaceClaim.field == "menu_item",
            )
            .all()
        )
    except Exception as exc:
        logger.exception("claims_fetch_failed place_id=%s error=%s", place_id, exc)
        return None

    if not claims:
        return None

    menu = build_canonical_menu(claims)

    if menu.item_count < MIN_TRUTH_ITEMS:
        return None

    truth = (
        db.query(PlaceTruth)
        .filter(
            PlaceTruth.place_id == place_id,
            PlaceTruth.truth_type == TRUTH_TYPE,
        )
        .one_or_none()
    )

    previous_menu = truth.sources_json if truth and isinstance(truth.sources_json, dict) else None
    serialized = _serialize_menu(menu, previous_menu)

    if previous_menu and previous_menu.get("menu_hash") == serialized.get("menu_hash"):
        return menu

    try:
        if truth:
            truth.truth_value = "menu"
            truth.sources_json = serialized
        else:
            db.add(
                PlaceTruth(
                    place_id=place_id,
                    truth_type=TRUTH_TYPE,
                    truth_value="menu",
                    sources_json=serialized,
                )
            )

        db.commit()

    except Exception as exc:
        db.rollback()
        logger.exception("truth_write_failed place_id=%s error=%s", place_id, exc)
        return None

    logger.info("truth_materialized place_id=%s items=%s", place_id, menu.item_count)

    return menu