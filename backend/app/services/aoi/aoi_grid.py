from __future__ import annotations

from math import floor
from typing import Tuple, List


# ---------------------------------------------------------
# Grid Configuration
# ---------------------------------------------------------

# Size of each grid cell (~1km depending on latitude)
GRID_SIZE_LAT = 0.01
GRID_SIZE_LNG = 0.01


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _snap(value: float, size: float) -> float:
    """
    Snap a coordinate to the nearest grid boundary.
    """
    return floor(value / size) * size


# ---------------------------------------------------------
# Grid Cell Functions
# ---------------------------------------------------------

def latlng_to_cell(lat: float, lng: float) -> Tuple[float, float]:
    """
    Convert a latitude/longitude coordinate to the
    grid cell anchor (bottom-left corner).
    """

    cell_lat = _snap(lat, GRID_SIZE_LAT)
    cell_lng = _snap(lng, GRID_SIZE_LNG)

    return cell_lat, cell_lng


def cell_id(lat: float, lng: float) -> str:
    """
    Generate a stable ID for a grid cell.
    """

    c_lat, c_lng = latlng_to_cell(lat, lng)

    return f"{round(c_lat,5)}:{round(c_lng,5)}"


def cell_bounds(lat: float, lng: float) -> Tuple[float, float, float, float]:
    """
    Return the bounding box of a grid cell.
    """

    c_lat, c_lng = latlng_to_cell(lat, lng)

    return (
        c_lat,
        c_lng,
        c_lat + GRID_SIZE_LAT,
        c_lng + GRID_SIZE_LNG,
    )


# ---------------------------------------------------------
# Neighbor Cells
# ---------------------------------------------------------

def neighbor_cells(lat: float, lng: float) -> List[str]:
    """
    Return IDs for surrounding grid cells
    (3x3 neighborhood).
    """

    c_lat, c_lng = latlng_to_cell(lat, lng)

    offsets = [-1, 0, 1]

    cells: List[str] = []

    for dy in offsets:
        for dx in offsets:

            n_lat = c_lat + dy * GRID_SIZE_LAT
            n_lng = c_lng + dx * GRID_SIZE_LNG

            cells.append(cell_id(n_lat, n_lng))

    return cells