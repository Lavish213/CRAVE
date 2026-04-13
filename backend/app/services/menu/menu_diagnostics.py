from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.db.models.menu_snapshot import MenuSnapshot
from app.db.models.place_truth import PlaceTruth
from app.db.models.menu_source import MenuSource


logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------

MAX_SNAPSHOTS = 25
MENU_TRUTH_TYPE = "menu"


# ---------------------------------------------------------
# SNAPSHOT ANALYSIS
# ---------------------------------------------------------

def _analyze_snapshots(
    snapshots: List[MenuSnapshot],
) -> Dict[str, Any]:

    total = len(snapshots)
    success = sum(1 for s in snapshots if s.success)
    failed = total - success

    item_counts = [s.item_count for s in snapshots if s.item_count]
    avg_items = round(sum(item_counts) / len(item_counts), 2) if item_counts else 0

    latest = snapshots[0] if snapshots else None

    return {
        "total": total,
        "success": success,
        "failed": failed,
        "avg_items": avg_items,
        "latest_snapshot_id": getattr(latest, "id", None),
        "latest_method": getattr(latest, "extraction_method", None),
        "latest_success": getattr(latest, "success", None),
        "latest_item_count": getattr(latest, "item_count", None),
    }


# ---------------------------------------------------------
# SOURCE ANALYSIS
# ---------------------------------------------------------

def _analyze_sources(
    sources: List[MenuSource],
) -> Dict[str, Any]:

    if not sources:
        return {
            "total": 0,
            "active": 0,
            "types": {},
        }

    active = sum(1 for s in sources if s.is_active)

    types: Dict[str, int] = {}

    for s in sources:
        t = getattr(s, "source_type", "unknown")
        types[t] = types.get(t, 0) + 1

    return {
        "total": len(sources),
        "active": active,
        "types": types,
    }


# ---------------------------------------------------------
# TRUTH ANALYSIS
# ---------------------------------------------------------

def _analyze_truth(
    truth: Optional[PlaceTruth],
) -> Dict[str, Any]:

    if not truth or not truth.sources_json:
        return {
            "exists": False,
            "item_count": 0,
            "section_count": 0,
            "last_hash": None,
        }

    data = truth.sources_json

    return {
        "exists": True,
        "item_count": data.get("metadata", {}).get("item_count", 0),
        "section_count": data.get("metadata", {}).get("section_count", 0),
        "last_hash": data.get("menu_hash"),
        "last_built_at": data.get("built_at"),
        "changes": data.get("changes"),
    }


# ---------------------------------------------------------
# MAIN DIAGNOSTICS
# ---------------------------------------------------------

def get_menu_diagnostics(
    *,
    db: Session,
    place_id: str,
) -> Dict[str, Any]:
    """
    Full observability for menu system.

    Covers:
    • snapshot health
    • source discovery
    • truth state
    • extraction signals
    """

    # -----------------------------------------------------
    # LOAD DATA
    # -----------------------------------------------------

    snapshots = (
        db.query(MenuSnapshot)
        .filter(MenuSnapshot.place_id == place_id)
        .order_by(MenuSnapshot.created_at.desc())
        .limit(MAX_SNAPSHOTS)
        .all()
    )

    sources = (
        db.query(MenuSource)
        .filter(MenuSource.place_id == place_id)
        .all()
    )

    truth = (
        db.query(PlaceTruth)
        .filter(
            PlaceTruth.place_id == place_id,
            PlaceTruth.truth_type == MENU_TRUTH_TYPE,
        )
        .one_or_none()
    )

    # -----------------------------------------------------
    # ANALYZE
    # -----------------------------------------------------

    snapshot_stats = _analyze_snapshots(snapshots)
    source_stats = _analyze_sources(sources)
    truth_stats = _analyze_truth(truth)

    # -----------------------------------------------------
    # HEALTH FLAGS
    # -----------------------------------------------------

    health_flags = {
        "has_sources": source_stats["total"] > 0,
        "has_successful_extraction": snapshot_stats["success"] > 0,
        "has_menu_truth": truth_stats["exists"],
        "low_item_count": truth_stats["item_count"] < 5 if truth_stats["exists"] else True,
        "high_failure_rate": snapshot_stats["failed"] > snapshot_stats["success"],
    }

    # -----------------------------------------------------
    # DEBUG SUMMARY
    # -----------------------------------------------------

    summary = {
        "place_id": place_id,
        "snapshots": snapshot_stats,
        "sources": source_stats,
        "truth": truth_stats,
        "health": health_flags,
    }

    logger.info(
        "menu_diagnostics place_id=%s truth=%s items=%s snapshots=%s",
        place_id,
        truth_stats["exists"],
        truth_stats["item_count"],
        snapshot_stats["total"],
    )

    return summary