from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Union


# -----------------------------------------------------
# CORE UTC CLOCK
# -----------------------------------------------------

def utc_now() -> datetime:
    """Authoritative UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """ISO timestamp for logs/telemetry."""
    return utc_now().isoformat()


# -----------------------------------------------------
# NORMALIZATION
# -----------------------------------------------------

def normalize_utc(dt: Optional[Union[datetime, str]]) -> Optional[datetime]:
    """
    Converts any datetime to UTC and guarantees tz-awareness.

    Handles:
    - None
    - Naive datetimes (assumed UTC)
    - Offset-aware datetimes
    - ISO strings
    """

    if dt is None:
        return None

    # Handle ISO string
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return None

    # If naive, assume UTC
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def to_utc(dt: Optional[Union[datetime, str]]) -> Optional[datetime]:
    """Alias for normalize_utc for readability."""
    return normalize_utc(dt)


# -----------------------------------------------------
# SAFE ISO
# -----------------------------------------------------

def safe_iso(dt: Optional[Union[datetime, str]]) -> Optional[str]:
    dt_utc = normalize_utc(dt)
    return dt_utc.isoformat() if dt_utc else None


# -----------------------------------------------------
# AGE HELPERS
# -----------------------------------------------------

def age_seconds(dt: Optional[Union[datetime, str]]) -> float:
    dt_utc = normalize_utc(dt)
    if not dt_utc:
        return 999999999.0

    now = utc_now()
    return (now - dt_utc).total_seconds()


def age_minutes(dt: Optional[Union[datetime, str]]) -> float:
    return age_seconds(dt) / 60.0


def age_hours(dt: Optional[Union[datetime, str]]) -> float:
    return age_seconds(dt) / 3600.0


def age_days(dt: Optional[Union[datetime, str]]) -> float:
    return age_seconds(dt) / 86400.0