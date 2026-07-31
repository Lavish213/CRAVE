# app/services/hitlist/suggest_intake.py
from __future__ import annotations
import logging
from typing import Optional
from sqlalchemy.orm import Session
from app.db.models.hitlist_suggestion import HitlistSuggestion
from app.services.social.platform_detect import detect_platform
from app.services.social.url_normalize import normalize_url
from app.services.hitlist.spam_guard import spam_guard
from app.services.discovery.discovery_service import ingest_candidate_v2

logger = logging.getLogger(__name__)

# Confidence for a hitlist suggestion's DiscoveryCandidate — higher than an
# unmatched social share (0.3, see share_parser_worker.py) since a human
# deliberately typed this place name rather than it being guessed from a
# scraped caption. Still well below the 0.72 promotion threshold on its
# own — one person's suggestion isn't enough; it needs to be corroborated
# by another suggestion, a share, or a GPS confirmation of the same place.
HITLIST_SUGGESTION_CANDIDATE_CONFIDENCE = 0.4


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

    clean_name = place_name.strip()

    suggestion = HitlistSuggestion(
        user_id=user_id,
        place_name=clean_name,
        city_hint=(city_hint or "").strip() or None,
        source_platform=platform,
        source_url=norm_url,
    )
    db.add(suggestion)
    db.flush()

    # Previously this table was write-only — nothing ever read these rows
    # back or turned them into anything. Feed it into the same
    # discovery-candidate pipeline every other "user found a place" input
    # uses (GPS confirmation, unmatched social shares) so suggestions
    # actually contribute toward getting a place added, instead of sitting
    # unread forever.
    try:
        ingest_candidate_v2(
            db=db,
            name=clean_name,
            city_name=suggestion.city_hint,
            source="user_hitlist_suggestion",
            confidence=HITLIST_SUGGESTION_CANDIDATE_CONFIDENCE,
            raw_payload={
                "hitlist_suggestion_id": suggestion.id,
                "source_url": norm_url,
                "source_platform": platform,
            },
            contributor_key=f"user_hitlist_suggestion:{user_id}",
        )
    except ValueError as exc:
        # No city could be resolved (no city_hint, no match) — the
        # suggestion itself is still saved above; just nothing to promote
        # toward yet.
        logger.debug("hitlist_suggestion_candidate_skip id=%s reason=%s", suggestion.id, exc)
    except Exception as exc:
        logger.warning("hitlist_suggestion_candidate_failed id=%s error=%s", suggestion.id, exc)

    return suggestion
