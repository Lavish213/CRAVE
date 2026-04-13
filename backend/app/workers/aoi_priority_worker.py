from __future__ import annotations
from typing import List, Dict
from app.services.aoi.aoi_priority import compute_aoi_priority

def compute_priorities(
    *,
    cells: List[Dict],
) -> List[Dict]:

    for c in cells:

        density = c.get("density_score", 0.0)
        velocity = c.get("velocity_score", 0.0)
        gap = c.get("gap_score", 0.0)

        c["priority"] = compute_aoi_priority(
            density,
            velocity,
            gap,
        )

    cells.sort(
        key=lambda x: x["priority"],
        reverse=True,
    )

    return cells
