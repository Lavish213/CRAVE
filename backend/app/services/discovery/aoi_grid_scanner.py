from __future__ import annotations

import logging
from typing import Dict, List


logger = logging.getLogger(__name__)


DEFAULT_GRID_SIZE_DEG = 0.02
MAX_CELLS = 10000


class AOIGridScanner:
    """
    Generates a grid of bounding boxes over an Area Of Interest (AOI).

    Each grid cell becomes a discovery query region.
    """

    def __init__(self, grid_size_deg: float = DEFAULT_GRID_SIZE_DEG) -> None:
        self.grid_size = grid_size_deg

    # -----------------------------------------------------
    # Public API
    # -----------------------------------------------------

    def generate_grid(
        self,
        *,
        lat_min: float,
        lat_max: float,
        lon_min: float,
        lon_max: float,
    ) -> List[Dict]:

        cells: List[Dict] = []

        lat = lat_min

        while lat < lat_max:

            lon = lon_min

            while lon < lon_max:

                cell = {
                    "lat_min": lat,
                    "lat_max": min(lat + self.grid_size, lat_max),
                    "lon_min": lon,
                    "lon_max": min(lon + self.grid_size, lon_max),
                }

                cells.append(cell)

                if len(cells) >= MAX_CELLS:
                    logger.warning(
                        "aoi_grid_limit_reached cells=%s",
                        len(cells),
                    )
                    return cells

                lon += self.grid_size

            lat += self.grid_size

        logger.info(
            "aoi_grid_generated cells=%s",
            len(cells),
        )

        return cells