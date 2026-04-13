from __future__ import annotations

from typing import Dict, List

from app.services.spatial.geohash_utils import spatial_hash


class SpatialIndex:
    """
    Simple in-memory spatial index for candidates.
    """

    def __init__(self):

        self.index: Dict[str, List[dict]] = {}

    def add(self, candidate: dict):

        lat = candidate.get("lat")
        lng = candidate.get("lng") or candidate.get("lon")

        if lat is None or lng is None:
            return

        key = spatial_hash(lat, lng)

        bucket = self.index.setdefault(key, [])

        bucket.append(candidate)

    def nearby(self, lat: float, lng: float) -> List[dict]:

        key = spatial_hash(lat, lng)

        return self.index.get(key, [])