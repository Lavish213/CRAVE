# app/services/hitlist/save_intake.py
from __future__ import annotations
import logging
from typing import Optional
from sqlalchemy.orm import Session
from app.db.models.hitlist_save import HitlistSave
from app.db.models.hitlist_dedup_key import HitlistDedupKey
from app.services.social.platform_detect import detect_platform
from app.services.social.url_normalize import normalize_url
from app.services.hitlist.dedup_engine import compute_dedup_key
from app.services.hitlist.spam_guard import spam_guard
from app.services.discovery.discovery_service import ingest_candidate_v2

logger = logging.getLogger(__name__)

# This is CRAVE's "I know the name (and maybe exactly where), no social link
# needed" manual add path — the counterpart to sharing a TikTok/IG link
# (share.py, confidence 0.3) and typing just a name+city with no coordinates
# (suggest_intake.py, confidence 0.4). A user who deliberately picked a spot
# on the map or typed a precise lat/lng is giving stronger evidence than a
# bare name guess, so this gets a slightly higher starting confidence. Still
# well under the 0.72 auto-promotion threshold on its own.
HITLIST_SAVE_CANDIDATE_CONFIDENCE = 0.45


def intake_hitlist_save(
    *,
    db: Session,
    user_id: str,
    place_name: str,
    source_url: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
) -> HitlistSave:
    if not spam_guard.allow_save(user_id):
        raise ValueError("Rate limit exceeded")

    norm_url = normalize_url(source_url)
    platform = detect_platform(norm_url) if norm_url else "unknown"

    dedup_key = compute_dedup_key(
        source_url=norm_url,
        place_name=place_name,
        lat=lat,
        lng=lng,
    )

    existing_dedup = (
        db.query(HitlistDedupKey)
        .filter(HitlistDedupKey.user_id == user_id, HitlistDedupKey.dedup_key == dedup_key)
        .one_or_none()
    )
    if existing_dedup:
        existing_save = (
            db.query(HitlistSave)
            .filter(HitlistSave.user_id == user_id, HitlistSave.dedup_key == dedup_key)
            .one_or_none()
        )
        if existing_save:
            return existing_save

    save = HitlistSave(
        user_id=user_id,
        place_name=place_name.strip(),
        source_platform=platform,
        source_url=norm_url,
        lat=lat,
        lng=lng,
        resolution_status="raw",
        dedup_key=dedup_key,
    )
    db.add(save)
    db.add(HitlistDedupKey(user_id=user_id, dedup_key=dedup_key))
    db.flush()

    # Previously this table was write-only, same dead end as
    # HitlistSuggestion before it — nothing ever turned a save into a real
    # place. Feed it into the same discovery-candidate pipeline as every
    # other "user found a place" input.
    try:
        ingest_candidate_v2(
            db=db,
            name=save.place_name,
            lat=lat,
            lng=lng,
            source="user_hitlist_save",
            confidence=HITLIST_SAVE_CANDIDATE_CONFIDENCE,
            raw_payload={
                "hitlist_save_id": save.id,
                "source_url": norm_url,
                "source_platform": platform,
            },
            contributor_key=f"user_hitlist_save:{user_id}",
        )
    except ValueError as exc:
        # No city could be resolved (no lat/lng and no other hint) — the
        # save itself is still recorded above; just nothing to promote
        # toward yet.
        logger.debug("hitlist_save_candidate_skip id=%s reason=%s", save.id, exc)
    except Exception as exc:
        logger.warning("hitlist_save_candidate_failed id=%s error=%s", save.id, exc)

    return save
