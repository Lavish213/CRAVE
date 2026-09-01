"""Shared, account-scoped mutations for memory attached to direct saves."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models.hitlist_save import HitlistSave


def mark_existing_save_visited(
    db: Session,
    *,
    user_id: str,
    place_id: str,
    visited_at: datetime | None = None,
) -> bool:
    """Mark the user's existing direct save visited without creating one.

    Ranking means the user ate at the place, but it must not silently add a
    place to Craves. The dedup-key predicate deliberately excludes discovery
    intake rows and prevents cross-account updates.
    """
    save = (
        db.query(HitlistSave)
        .filter(
            HitlistSave.user_id == user_id,
            HitlistSave.place_id == place_id,
            HitlistSave.dedup_key == f"save:{user_id}:{place_id}",
        )
        .one_or_none()
    )
    if save is None:
        return False

    save.visited = True
    if save.visited_at is None:
        save.visited_at = visited_at or datetime.now(timezone.utc)
    db.flush()
    return True
