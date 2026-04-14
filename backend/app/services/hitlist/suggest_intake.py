# app/services/hitlist/suggest_intake.py
from __future__ import annotations
from typing import Optional
from sqlalchemy.orm import Session
from app.db.models.hitlist_suggestion import HitlistSuggestion
from app.services.social.platform_detect import detect_platform
from app.services.social.url_normalize import normalize_url
from app.services.hitlist.spam_guard import spam_guard


def intake_suggestion(
    *,
    db: Session,
    user_id: str,
    place_name: str,
    source_url: Optional[str] = None,
    city_hint: Optional[str] = None,
) -> HitlistSuggestion:
    if not spam_guard.allow_suggest(user_id):
        raise ValueError("Rate limit exceeded")

    norm_url = normalize_url(source_url)
    platform = detect_platform(norm_url) if norm_url else "unknown"

    suggestion = HitlistSuggestion(
        user_id=user_id,
        place_name=place_name.strip(),
        city_hint=(city_hint or "").strip() or None,
        source_platform=platform,
        source_url=norm_url,
    )
    db.add(suggestion)
    db.flush()
    return suggestion
