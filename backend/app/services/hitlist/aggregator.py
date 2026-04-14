# app/services/hitlist/aggregator.py
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def aggregate_saves(saves: List[dict], window_hours: int = 24) -> List[dict]:
    """
    Input:  [{"place_name": str, "city": str, "timestamp": datetime}, ...]
    Output: [{"place_name", "city", "save_count", "recent_velocity", "score"}, ...]
            sorted by score DESC
    """
    if not saves:
        return []

    cutoff = _utcnow() - timedelta(hours=window_hours)
    grouped: Dict[str, List[dict]] = defaultdict(list)
    for s in saves:
        grouped[f"{s['place_name']}|{s.get('city', '')}"].append(s)

    results = []
    for key, items in grouped.items():
        name, city = key.split("|", 1)
        total = len(items)
        recent = sum(1 for x in items if x["timestamp"] >= cutoff)
        recency_s = recent / max(total, 1)
        volume_s = min(total / 100.0, 1.0)
        score = round(recency_s * 0.70 + volume_s * 0.30, 6)
        results.append({
            "place_name": name,
            "city": city,
            "save_count": total,
            "recent_velocity": recent,
            "score": score,
        })

    return sorted(results, key=lambda x: x["score"], reverse=True)
