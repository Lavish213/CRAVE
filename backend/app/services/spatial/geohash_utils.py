from __future__ import annotations

import math


EARTH_RADIUS_KM = 6371


def normalize_lat(lat: float) -> float:
    return max(min(lat, 90.0), -90.0)


def normalize_lng(lng: float) -> float:
    if lng > 180:
        lng -= 360
    if lng < -180:
        lng += 360
    return lng


def spatial_hash(
    lat: float,
    lng: float,
    precision: int = 4,
) -> str:
    """
    Lightweight spatial bucket key.

    Used for candidate clustering and dedupe acceleration.

    Example
    -------
    37.7749, -122.4194 → 3777_-12241
    """

    lat = normalize_lat(lat)
    lng = normalize_lng(lng)

    factor = 10 ** precision

    lat_bucket = int(lat * factor)
    lng_bucket = int(lng * factor)

    return f"{lat_bucket}_{lng_bucket}"


def haversine_distance_km(
    lat1: float,
    lng1: float,
    lat2: float,
    lng2: float,
) -> float:
    """
    Calculate distance between two points.
    """

    lat1 = math.radians(lat1)
    lng1 = math.radians(lng1)

    lat2 = math.radians(lat2)
    lng2 = math.radians(lng2)

    dlat = lat2 - lat1
    dlng = lng2 - lng1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_KM * c