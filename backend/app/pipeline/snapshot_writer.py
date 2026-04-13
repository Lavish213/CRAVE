from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import SQLAlchemyError

from app.db.models.menu_snapshot import MenuSnapshot
from app.db.session import SessionLocal


logger = logging.getLogger(__name__)


def _clean_str(value: Any) -> str | None:
    if value is None:
        return None

    try:
        cleaned = str(value).strip()
        return cleaned or None
    except Exception:
        return None


def _safe_price(value: Any) -> float | None:
    try:
        return round(float(value), 2) if value is not None else None
    except (TypeError, ValueError):
        return None


def _normalize_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []

    normalized: list[dict[str, Any]] = []

    for row in items:
        if not isinstance(row, dict):
            continue

        name = _clean_str(row.get("name"))
        if not name:
            continue

        normalized.append(
            {
                "name": name,
                "category": _clean_str(row.get("category")),
                "price": _safe_price(row.get("price")),
                "description": _clean_str(row.get("description")),
                "image": _clean_str(row.get("image")),
            }
        )

    return normalized


class MenuSnapshotWriter:
    """
    Production-safe immutable snapshot writer.

    Guarantees:
    • isolated DB session
    • crash-safe writes
    • input normalization
    • never blocks caller pipeline
    • consistent logging
    """

    def write(
        self,
        *,
        place_id: str,
        extraction_method: str,
        source_url: str | None = None,
        success: bool = True,
        raw_payload: Dict[str, Any] | None = None,
        normalized_items: List[Dict[str, Any]] | None = None,
        error_message: str | None = None,
    ) -> str | None:
        clean_place_id = _clean_str(place_id)
        method = _clean_str(extraction_method)

        if not clean_place_id:
            logger.error("menu_snapshot_invalid_missing_place_id")
            return None

        if not method:
            logger.error(
                "menu_snapshot_invalid_missing_method place_id=%s",
                clean_place_id,
            )
            return None

        cleaned_url = _clean_str(source_url)
        cleaned_error = _clean_str(error_message)

        safe_raw_payload = raw_payload if isinstance(raw_payload, dict) else None
        safe_items = _normalize_items(normalized_items)
        item_count = len(safe_items)

        db = SessionLocal()

        try:
            snapshot = MenuSnapshot(
                place_id=clean_place_id,
                extraction_method=method,
                source_url=cleaned_url,
                success=bool(success),
                item_count=item_count,
                raw_payload=safe_raw_payload,
                normalized_items=safe_items,
                error_message=cleaned_error,
            )

            db.add(snapshot)
            db.commit()
            db.refresh(snapshot)

            logger.info(
                "menu_snapshot_written place_id=%s snapshot_id=%s method=%s success=%s items=%s",
                clean_place_id,
                snapshot.id,
                method,
                bool(success),
                item_count,
            )

            return snapshot.id

        except SQLAlchemyError:
            db.rollback()
            logger.exception(
                "menu_snapshot_db_error place_id=%s method=%s",
                clean_place_id,
                method,
            )
            return None

        except Exception:
            db.rollback()
            logger.exception(
                "menu_snapshot_unexpected_error place_id=%s method=%s",
                clean_place_id,
                method,
            )
            return None

        finally:
            db.close()


class SnapshotWriter:
    """
    Backward-compat shim for older callers.

    Intentionally returns entities unchanged.
    """

    def write(self, entities: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        if not isinstance(entities, list):
            return []
        return entities