from __future__ import annotations
from typing import List, Dict
from .aoi_priority import compute_aoi_priority

def rank_cells(cells: List[Dict]) -> List[Dict]:

    for cell in cells:

        density = cell.get("density_score", 0.0)
        velocity = cell.get("velocity_score", 0.0)
        gap = cell.get("gap_score", 0.0)

        cell["priority"] = compute_aoi_priority(
            density,
            velocity,
            gap,
        )

    cells.sort(
        key=lambda c: c["priority"],
        reverse=True,
    )

    return cells
