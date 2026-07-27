from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import delete

from app.db.models.menu_item import MenuItem
from app.db.models.place_truth import PlaceTruth
from app.services.menu.normalization.fingerprint import build_menu_fingerprint


logger = logging.getLogger(__name__)


class MenuPublisher:
    """
    Materializes PlaceTruth (menu JSON) → MenuItem table rows.

    Rules:
    - NOT primary source of truth — PlaceTruth is.
    - Uses the SAME session as the caller — no internal SessionLocal().
    - delete+insert is atomic within the passed session.
    - Sets fingerprint on every row — required by schema contract.
    - price_cents stored as INTEGER — never float.
    """

    def publish(self, *, place_id: str, db: Session) -> int:
        """
        Publish menu truth to menu_items table.

        Args:
            place_id: the place to publish for
            db: the caller's session — used directly, not wrapped

        Returns:
            count of MenuItem rows written
        """
        if not place_id:
            raise ValueError("MISSING_PLACE_ID")

        truth: Optional[PlaceTruth] = (
            db.query(PlaceTruth)
            .filter(
                PlaceTruth.place_id == place_id,
                PlaceTruth.truth_type == "menu",
            )
            .one_or_none()
        )

        if not truth or not truth.sources_json:
            logger.warning("menu_publish_no_truth place_id=%s", place_id)
            return 0

        sections = truth.sources_json.get("sections", []) or []

        if not sections:
            logger.warning("menu_publish_empty_truth place_id=%s", place_id)
            return 0

        try:
            # Delete existing rows for this place (within caller's transaction)
            db.execute(delete(MenuItem).where(MenuItem.place_id == place_id))

            created_count = 0

            for section in sections:
                section_name = (section.get("name") or "Other").strip() or "Other"

                for item in section.get("items", []) or []:
                    name = (item.get("name") or "").strip()
                    if not name:
                        continue

                    # price_cents must stay integer — it was stored as int in truth JSON
                    raw_price = item.get("price_cents")
                    price_cents: Optional[int] = None
                    if raw_price is not None:
                        try:
                            price_cents = int(raw_price)
                            if price_cents < 0:
                                price_cents = None
                        except (TypeError, ValueError):
                            price_cents = None

                    # Fingerprint: match the normalization/fingerprint.py contract
                    fp = (
                        item.get("fingerprint")
                        or build_menu_fingerprint(
                            name=name,
                            section=section_name,
                            currency="usd",
                        )
                    )

                    try:
                        db.add(
                            MenuItem(
                                place_id=place_id,
                                name=name,
                                fingerprint=fp,
                                category=section_name,
                                price_cents=price_cents,
                                description=item.get("description"),
                                image=None,  # item-level images handled by MenuImageBridge
                                confidence_score=float(item.get("confidence") or 0.0),
                                source_type="truth",
                            )
                        )
                        created_count += 1

                    except Exception as exc:
                        logger.warning(
                            "menu_item_skipped place_id=%s name=%r error=%s",
                            place_id, name, exc,
                        )

            db.flush()

            logger.info(
                "menu_published place_id=%s item_count=%s",
                place_id,
                created_count,
            )

            return created_count

        except SQLAlchemyError as exc:
            # Caller is responsible for rollback
            logger.error("menu_publish_failed place_id=%s error=%s", place_id, exc)
            raise
