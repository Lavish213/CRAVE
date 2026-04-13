from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.orm import Session

from app.core.time import utc_now_iso
from app.services.discovery.promotion_orchestrator_v2 import promote_ready_candidates_v2


def run_discovery_pipeline_v2(
    *,
    db: Session,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    V2 Discovery Pipeline

    Stage order:
    1) Promote eligible candidates
    2) Truth resolution occurs inside promote_service_v2

    Returns structured stats for logging / monitoring.
    """

    started_at = utc_now_iso()

    try:
        promoted_count = promote_ready_candidates_v2(
            db=db,
            limit=limit,
        )

        finished_at = utc_now_iso()

        return {
            "pipeline": "discovery_v2",
            "started_at": started_at,
            "finished_at": finished_at,
            "limit": limit,
            "promoted": promoted_count,
            "error": None,
        }

    except Exception as e:
        # Critical: don’t leave the session in a broken transaction state
        db.rollback()

        finished_at = utc_now_iso()

        return {
            "pipeline": "discovery_v2",
            "started_at": started_at,
            "finished_at": finished_at,
            "limit": limit,
            "promoted": 0,
            "error": f"{type(e).__name__}: {e}",
        }