from __future__ import annotations
from typing import List, Dict
from sqlalchemy.orm import Session
from app.services.aoi.aoi_grid import latlng_to_cell, cell_id
from app.services.aoi.aoi_density import compute_density_score

def scan_cells(
    db: Session,
    *,
    places: List[Dict],
) -> List[Dict]:

    cell_map: Dict[str, int] = {}

    for p in places:

        lat = p["lat"]
        lng = p["lng"]

        cid = cell_id(lat, lng)

        cell_map[cid] = cell_map.get(cid, 0) + 1

    results: List[Dict] = []

    for cid, count in cell_map.items():

        density = compute_density_score(
            places_in_cell=count
        )

        results.append(
            {
                "cell_id": cid,
                "place_count": count,
                "density_score": density,
            }
        )

    return results
