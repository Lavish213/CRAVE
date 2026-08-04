# app/services/images/exif_reader.py
"""
Reads capture metadata off an upload before it's discarded.

app/utils/image_pipeline.py calls strip_exif() as the last step of both
process_image() and process_thumbnail() — correct for privacy on the
stored file (GPS coordinates of a user's location should not be served
publicly), but it means the metadata has to be extracted *first* or the
strongest authenticity signal we have is destroyed unread.

What this buys: a photo whose embedded GPS sits within a short walk of the
place it was uploaded to is near-certainly a real visit. That's the signal
Airbnb's own case managers use, and neither Yelp nor Google surfaces it to
users. Nothing here is proof on its own — metadata is trivially editable —
so it's treated as corroboration that raises trust, never as a gate that
rejects on absence. Plenty of legitimate photos carry no EXIF at all
(screenshots of a menu, anything routed through a messaging app, iOS
"remove location" sharing), so absence is neutral, not suspicious.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS

logger = logging.getLogger(__name__)

# A photo taken this close to the place's coordinates is treated as
# corroborating a real visit. Loose enough for GPS drift in an urban
# canyon, tight enough that it doesn't cover the next block over.
GPS_MATCH_RADIUS_M = 120.0

# Capture timestamps outside this window are ignored rather than trusted —
# a wildly future date means a wrong device clock or edited metadata.
_MAX_FUTURE_SKEW_DAYS = 2


@dataclass(frozen=True)
class ExifReport:
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    captured_at: Optional[datetime] = None
    camera_make: Optional[str] = None
    software: Optional[str] = None

    @property
    def has_gps(self) -> bool:
        return self.gps_lat is not None and self.gps_lng is not None


def _to_degrees(value) -> Optional[float]:
    """EXIF stores coordinates as ((deg),(min),(sec)) rationals."""
    try:
        d, m, s = value
        return float(d) + float(m) / 60.0 + float(s) / 3600.0
    except Exception:
        return None


def _parse_gps(gps_raw: dict) -> tuple[Optional[float], Optional[float]]:
    try:
        tags = {GPSTAGS.get(k, k): v for k, v in gps_raw.items()}

        lat = _to_degrees(tags.get("GPSLatitude"))
        lng = _to_degrees(tags.get("GPSLongitude"))
        if lat is None or lng is None:
            return None, None

        # Hemisphere refs — without these a southern/western photo lands in
        # the wrong hemisphere entirely.
        if str(tags.get("GPSLatitudeRef", "N")).upper().startswith("S"):
            lat = -lat
        if str(tags.get("GPSLongitudeRef", "E")).upper().startswith("W"):
            lng = -lng

        if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
            return None, None
        # Exactly (0, 0) is Null Island — a placeholder, not a location.
        if lat == 0.0 and lng == 0.0:
            return None, None

        return lat, lng
    except Exception:
        return None, None


def _parse_timestamp(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        # EXIF DateTimeOriginal format: "2026:08:03 14:22:31"
        parsed = datetime.strptime(str(raw).strip(), "%Y:%m:%d %H:%M:%S")
        parsed = parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None

    now = datetime.now(timezone.utc)
    if (parsed - now).days > _MAX_FUTURE_SKEW_DAYS:
        return None
    return parsed


def read_exif(image: Image.Image) -> ExifReport:
    """Extract capture metadata. Never raises; absence is normal."""
    try:
        raw = image.getexif()
        if not raw:
            return ExifReport()

        decoded = {TAGS.get(k, k): v for k, v in raw.items()}

        gps_lat = gps_lng = None
        try:
            # GPS lives in its own IFD, not the top-level tag dict.
            gps_ifd = raw.get_ifd(0x8825)
            if gps_ifd:
                gps_lat, gps_lng = _parse_gps(gps_ifd)
        except Exception:
            pass

        def _clean(value, limit: int) -> Optional[str]:
            if not value:
                return None
            text = str(value).strip()
            return text[:limit] or None

        return ExifReport(
            gps_lat=gps_lat,
            gps_lng=gps_lng,
            captured_at=_parse_timestamp(
                decoded.get("DateTimeOriginal") or decoded.get("DateTime")
            ),
            camera_make=_clean(decoded.get("Make"), 64),
            software=_clean(decoded.get("Software"), 64),
        )
    except Exception as exc:
        logger.debug("exif_read_failed error=%s", exc)
        return ExifReport()


def meters_between(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Equirectangular approximation — accurate well under a kilometre,
    matching the helper already used in api/v1/routes/nearby.py."""
    deg_to_m = 111_320.0
    dlat = (lat2 - lat1) * deg_to_m
    dlng = (lng2 - lng1) * deg_to_m * math.cos(math.radians(lat1))
    return math.sqrt(dlat ** 2 + dlng ** 2)


def gps_matches_place(
    exif: ExifReport,
    *,
    place_lat: Optional[float],
    place_lng: Optional[float],
) -> bool:
    """True only when EXIF GPS positively corroborates the place. Missing
    metadata on either side returns False — unverified, not rejected."""
    if not exif.has_gps or place_lat is None or place_lng is None:
        return False
    distance = meters_between(exif.gps_lat, exif.gps_lng, place_lat, place_lng)
    return distance <= GPS_MATCH_RADIUS_M
