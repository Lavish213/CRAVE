from __future__ import annotations

from dataclasses import dataclass
import math


EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True)
class BoundingBox:
    min_lat: float
    max_lat: float
    min_lng: float
    max_lng: float


def bounding_box(
    lat: float,
    lng: float,
    radius_km: float,
) -> BoundingBox:

    lat_rad = math.radians(lat)

    lat_delta = radius_km / EARTH_RADIUS_KM
    lng_delta = radius_km / (EARTH_RADIUS_KM * math.cos(lat_rad))

    min_lat = lat - math.degrees(lat_delta)
    max_lat = lat + math.degrees(lat_delta)
    min_lng = lng - math.degrees(lng_delta)
    max_lng = lng + math.degrees(lng_delta)

    return BoundingBox(
        min_lat=min_lat,
        max_lat=max_lat,
        min_lng=min_lng,
        max_lng=max_lng,
    )