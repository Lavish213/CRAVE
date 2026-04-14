# app/services/hitlist/analytics.py
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from app.db.models.hitlist_save import HitlistSave


def get_hitlist_analytics(db: Session) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    saves_today = db.execute(
        select(func.count(HitlistSave.id))
        .where(HitlistSave.created_at >= today_start)
    ).scalar_one()

    unresolved = db.execute(
        select(func.count(HitlistSave.id))
        .where(HitlistSave.place_id.is_(None))
    ).scalar_one()

    promoted = db.execute(
        select(func.count(HitlistSave.id))
        .where(HitlistSave.resolution_status == "promoted")
    ).scalar_one()

    top_rows = db.execute(
        select(HitlistSave.place_name, func.count(HitlistSave.id).label("cnt"))
        .group_by(HitlistSave.place_name)
        .order_by(func.count(HitlistSave.id).desc())
        .limit(10)
    ).all()

    return {
        "saves_today": saves_today,
        "unresolved_count": unresolved,
        "promoted_count": promoted,
        "top_saved_places": [
            {"place_name": r.place_name, "save_count": r.cnt} for r in top_rows
        ],
    }
