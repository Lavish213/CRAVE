# app/services/hitlist/get_user_hitlist.py
from __future__ import annotations
from typing import List
from sqlalchemy.orm import Session
from app.db.models.hitlist_save import HitlistSave


def get_user_hitlist(
    *,
    db: Session,
    user_id: str,
    include_resolved: bool = True,
    include_unresolved: bool = True,
    limit: int = 100,
) -> List[HitlistSave]:
    q = db.query(HitlistSave).filter(HitlistSave.user_id == user_id)
    if include_resolved and not include_unresolved:
        q = q.filter(HitlistSave.place_id.isnot(None))
    elif include_unresolved and not include_resolved:
        q = q.filter(HitlistSave.place_id.is_(None))
    return q.order_by(HitlistSave.created_at.desc()).limit(max(1, min(500, limit))).all()
