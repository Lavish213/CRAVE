from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.session import get_db
from app.services.cache.response_cache import response_cache

router = APIRouter()

_HEALTH_CACHE_KEY = "__health_check__"


@router.get("/health")
def health(db: Session = Depends(get_db)):

    # --- DB check ---
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    # --- Cache check ---
    cache_status = "ok"
    try:
        response_cache.set(_HEALTH_CACHE_KEY, "1", ttl_seconds=10)
        val = response_cache.get(_HEALTH_CACHE_KEY)
        if val != "1":
            cache_status = "error"
    except Exception:
        cache_status = "error"

    # --- Worker ---
    worker_status = "ok"

    # --- Aggregate status ---
    if db_status == "error":
        top_status = "error"
    elif cache_status == "error":
        top_status = "degraded"
    else:
        top_status = "ok"

    return {
        "status": top_status,
        "db": db_status,
        "cache": cache_status,
        "worker": worker_status,
    }
