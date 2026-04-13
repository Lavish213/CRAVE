from __future__ import annotations
from typing import List
from .aoi_grid import GRID_SIZE_LAT, GRID_SIZE_LNG, latlng_to_cell, cell_id

def ring_cells(lat: float, lng: float, ring: int) -> List[str]:
    c_lat, c_lng = latlng_to_cell(lat,lng)
    results: List[str] = []
    for dy in range(-ring, ring+1):
        for dx in range(-ring, ring+1):
            if abs(dy) != ring and abs(dx) != ring:
                continue
            n_lat = c_lat + dy * GRID_SIZE_LAT
            n_lng = c_lng + dx * GRID_SIZE_LNG
            results.append(cell_id(n_lat,n_lng))
    return results

def multi_ring_cells(lat: float, lng: float, rings: int = 2) -> List[str]:
    cells: List[str] = []
    for r in range(1, rings+1):
        cells.extend(ring_cells(lat,lng,r))
    return cells
