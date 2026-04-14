# app/services/hitlist/delete_save.py
from __future__ import annotations
from sqlalchemy.orm import Session
from app.db.models.hitlist_save import HitlistSave
from app.db.models.hitlist_dedup_key import HitlistDedupKey


def delete_hitlist_save(*, db: Session, user_id: str, place_name: str) -> bool:
    save = (
        db.query(HitlistSave)
        .filter(HitlistSave.user_id == user_id, HitlistSave.place_name == place_name)
        .first()
    )
    if not save:
        return False
    db.query(HitlistDedupKey).filter(
        HitlistDedupKey.user_id == user_id,
        HitlistDedupKey.dedup_key == save.dedup_key,
    ).delete()
    db.delete(save)
    db.flush()
    return True
