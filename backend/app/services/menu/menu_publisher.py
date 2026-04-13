from __future__ import annotations

import logging
from typing import Dict, Any, List

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import delete

from app.db.session import SessionLocal
from app.db.models.menu_snapshot import MenuSnapshot
from app.db.models.menu_item import MenuItem
from app.db.models.place_truth import PlaceTruth


logger = logging.getLogger(__name__)


class MenuPublisher:
    """
    Optional materialization layer.

    Converts:
        PlaceTruth (menu JSON)
            ↓
        MenuItem table (cache)

    Notes:
    • NOT primary source of truth
    • Safe to disable entirely
    """

    def publish(self, *, place_id: str) -> int:

        if not place_id:
            raise ValueError("MISSING_PLACE_ID")

        db = SessionLocal()

        try:
            # -----------------------------------------------------
            # LOAD TRUTH (PRIMARY SOURCE)
            # -----------------------------------------------------

            truth: PlaceTruth | None = (
                db.query(PlaceTruth)
                .filter(
                    PlaceTruth.place_id == place_id,
                    PlaceTruth.truth_type == "menu",
                )
                .one_or_none()
            )

            if not truth or not truth.sources_json:
                logger.warning(
                    "menu_publish_no_truth place_id=%s",
                    place_id,
                )
                return 0

            sections = truth.sources_json.get("sections", [])

            items: List[Dict[str, Any]] = []

            for section in sections:
                for item in section.get("items", []):
                    items.append({
                        "name": item.get("name"),
                        "category": section.get("name"),
                        "price": item.get("price_cents"),
                        "description": item.get("description"),
                        "image": None,
                    })

            if not items:
                logger.warning(
                    "menu_publish_empty_truth place_id=%s",
                    place_id,
                )
                return 0

            # -----------------------------------------------------
            # REPLACE OLD MENU
            # -----------------------------------------------------

            db.execute(
                delete(MenuItem).where(MenuItem.place_id == place_id)
            )

            created_count = 0

            for row in items:
                try:
                    db.add(
                        MenuItem(
                            place_id=place_id,
                            name=row.get("name"),
                            category=row.get("category"),
                            price=row.get("price"),
                            description=row.get("description"),
                            image=row.get("image"),
                            raw_payload=row,
                        )
                    )
                    created_count += 1

                except Exception as exc:
                    logger.warning(
                        "menu_item_skipped place_id=%s error=%s",
                        place_id,
                        exc,
                    )

            db.flush()
            db.commit()

            logger.info(
                "menu_published place_id=%s item_count=%s",
                place_id,
                created_count,
            )

            return created_count

        except SQLAlchemyError as exc:
            db.rollback()

            logger.error(
                "menu_publish_failed place_id=%s error=%s",
                place_id,
                exc,
            )

            raise

        finally:
            db.close()