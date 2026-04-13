from __future__ import annotations

import logging
import re
import unicodedata
import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.place import Place


logger = logging.getLogger(__name__)


# =========================================================
# RESULT
# =========================================================

@dataclass(slots=True)
class PlaceWriteResult:
    place_id: Optional[str]
    created: bool
    reason: str


# =========================================================
# MAIN ENTRY
# =========================================================

def create_or_get_place(
    *,
    db: Session,
    city_id: str,
    name: str,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    website: Optional[str] = None,
    grubhub_url: Optional[str] = None,
    is_active: bool = True,
) -> PlaceWriteResult:

    if not db:
        return PlaceWriteResult(None, False, "missing_db")

    clean_city_id = _clean_str(city_id)
    clean_name = _clean_name(name)

    if not clean_city_id or not clean_name:
        return PlaceWriteResult(None, False, "invalid_input")

    clean_lat = _safe_float(lat)
    clean_lng = _safe_float(lng)
    clean_website = _clean_url(website)
    clean_grubhub = _clean_url(grubhub_url)

    # 🔥 normalized lookup key (prevents "McDonald's" vs "McDonalds")
    lookup_name = _normalize_lookup(clean_name)

    # -----------------------------------------------------
    # STEP 1 — LOOKUP EXISTING
    # -----------------------------------------------------

    existing = (
        db.query(Place)
        .filter(
            Place.city_id == clean_city_id,
            Place.name == clean_name,
        )
        .first()
    )

    if not existing:
        # 🔥 fallback lookup (normalized match)
        existing = (
            db.query(Place)
            .filter(Place.city_id == clean_city_id)
            .all()
        )

        for p in existing:
            if _normalize_lookup(p.name) == lookup_name:
                existing = p
                break
        else:
            existing = None

    if existing:
        _safe_update_place(
            db=db,
            place=existing,
            lat=clean_lat,
            lng=clean_lng,
            website=clean_website,
            grubhub_url=clean_grubhub,
        )

        return PlaceWriteResult(existing.id, False, "existing")

    # -----------------------------------------------------
    # STEP 2 — CREATE NEW
    # -----------------------------------------------------

    new_place = Place(
        id=str(uuid.uuid4()),
        name=clean_name,
        city_id=clean_city_id,
        lat=clean_lat,
        lng=clean_lng,
        website=clean_website,
        grubhub_url=clean_grubhub,
        is_active=is_active,
    )

    try:
        db.add(new_place)
        db.commit()

        logger.info(
            "place_created id=%s name='%s'",
            new_place.id,
            clean_name,
        )

        return PlaceWriteResult(new_place.id, True, "created")

    except IntegrityError:
        db.rollback()

        # -------------------------------------------------
        # RACE CONDITION RECOVERY
        # -------------------------------------------------

        existing = (
            db.query(Place)
            .filter(
                Place.city_id == clean_city_id,
                Place.name == clean_name,
            )
            .first()
        )

        if existing:
            logger.warning(
                "place_race_recovered name='%s' id=%s",
                clean_name,
                existing.id,
            )

            return PlaceWriteResult(existing.id, False, "race_recovered")

        logger.exception("place_insert_failed name='%s'", clean_name)
        return PlaceWriteResult(None, False, "insert_failed")

    except Exception as exc:
        db.rollback()
        logger.exception(
            "place_insert_error name='%s' error=%s",
            clean_name,
            exc,
        )
        return PlaceWriteResult(None, False, "error")


# =========================================================
# SAFE UPDATE (NO OVERWRITE)
# =========================================================

def _safe_update_place(
    *,
    db: Session,
    place: Place,
    lat: Optional[float],
    lng: Optional[float],
    website: Optional[str],
    grubhub_url: Optional[str],
):
    updated = False

    if lat is not None and place.lat is None:
        place.lat = lat
        updated = True

    if lng is not None and place.lng is None:
        place.lng = lng
        updated = True

    if website and not place.website:
        place.website = website
        updated = True

    if grubhub_url and not getattr(place, "grubhub_url", None):
        place.grubhub_url = grubhub_url
        updated = True

    if updated:
        try:
            db.commit()
            logger.info("place_updated id=%s", place.id)
        except Exception:
            db.rollback()
            logger.warning("place_update_failed id=%s", place.id)


# =========================================================
# NORMALIZATION
# =========================================================

def _clean_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None

    name = _normalize_unicode(name)
    name = name.strip()

    name = re.sub(r"[^\w\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()

    return name if name else None


def _normalize_lookup(name: str) -> str:
    name = name.lower()

    for word in ["restaurant", "cafe", "grill", "kitchen", "bar"]:
        name = name.replace(word, "")

    name = re.sub(r"[^\w\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()

    return name


def _clean_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None

    try:
        url = str(url).strip()
    except Exception:
        return None

    if not url:
        return None

    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    return url


def _clean_str(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        s = str(value).strip()
        return s if s else None
    except Exception:
        return None


def _safe_float(value) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except Exception:
        return None


def _normalize_unicode(text: str) -> str:
    try:
        text = unicodedata.normalize("NFKD", text)
        text = text.encode("ascii", "ignore").decode("ascii")
    except Exception:
        pass
    return text