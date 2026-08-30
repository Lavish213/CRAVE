from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from app.services.cache.response_cache import response_cache


FEED_SNAPSHOT_TTL_SECONDS = 900
FEED_SNAPSHOT_PREFIX = "feed-snapshot:"


@dataclass(frozen=True)
class FeedCursorPage:
    place_ids: list[str]
    total: int
    next_cursor: str | None


def build_scope(
    *,
    city_id: str | None,
    lat: float | None,
    lng: float | None,
    radius_miles: float,
    page_size: int,
) -> str:
    return json.dumps(
        {
            "city_id": city_id or None,
            "lat": round(lat, 5) if lat is not None else None,
            "lng": round(lng, 5) if lng is not None else None,
            "radius_miles": round(radius_miles, 2),
            "page_size": page_size,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def create_snapshot(
    *,
    scope: str,
    place_ids: list[str],
    total: int,
    page_size: int,
) -> FeedCursorPage:
    token = uuid.uuid4().hex
    snapshot = {
        "scope": scope,
        "place_ids": list(place_ids),
        "total": max(0, int(total)),
    }
    response_cache.set(
        f"{FEED_SNAPSHOT_PREFIX}{token}",
        snapshot,
        ttl_seconds=FEED_SNAPSHOT_TTL_SECONDS,
    )
    return _page(snapshot=snapshot, token=token, offset=0, page_size=page_size)


def read_snapshot(*, cursor: str, scope: str, page_size: int) -> FeedCursorPage | None:
    token, offset = _parse_cursor(cursor)
    if token is None:
        return None
    snapshot = response_cache.get(f"{FEED_SNAPSHOT_PREFIX}{token}")
    if not isinstance(snapshot, dict):
        return None
    if snapshot.get("scope") != scope:
        raise ValueError("scope_mismatch")
    return _page(snapshot=snapshot, token=token, offset=offset, page_size=page_size)


def _parse_cursor(cursor: str) -> tuple[str | None, int]:
    try:
        token, raw_offset = cursor.rsplit(".", 1)
        offset = int(raw_offset)
    except (AttributeError, TypeError, ValueError):
        return None, 0
    if len(token) != 32 or offset < 0:
        return None, 0
    return token, offset


def _page(
    *,
    snapshot: dict[str, Any],
    token: str,
    offset: int,
    page_size: int,
) -> FeedCursorPage:
    ids = snapshot.get("place_ids")
    if not isinstance(ids, list):
        ids = []
    place_ids = [str(place_id) for place_id in ids[offset : offset + page_size]]
    next_offset = offset + len(place_ids)
    next_cursor = f"{token}.{next_offset}" if next_offset < len(ids) else None
    return FeedCursorPage(
        place_ids=place_ids,
        total=max(0, int(snapshot.get("total") or 0)),
        next_cursor=next_cursor,
    )
