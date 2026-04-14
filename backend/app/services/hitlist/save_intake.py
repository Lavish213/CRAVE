# app/services/hitlist/save_intake.py
from __future__ import annotations
from typing import Optional
from sqlalchemy.orm import Session
from app.db.models.hitlist_save import HitlistSave
from app.db.models.hitlist_dedup_key import HitlistDedupKey
from app.services.social.platform_detect import detect_platform
from app.services.social.url_normalize import normalize_url
from app.services.hitlist.dedup_engine import compute_dedup_key
from app.services.hitlist.spam_guard import spam_guard


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
    return save
