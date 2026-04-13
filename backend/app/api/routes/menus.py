from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas.menu import MenuOut
from app.db.session import get_db
from app.services.truth.truth_reader import get_menu_truth


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/places",
    tags=["menus"],
)


@router.get(
    "/{place_id}/menu",
    response_model=MenuOut,
)
def get_place_menu(
    place_id: str,
    db: Session = Depends(get_db),
):
    """
    Return canonical menu for a place.
    """

    menu = get_menu_truth(
        db=db,
        place_id=place_id,
    )

    if not menu:
        logger.info("menu_not_found place_id=%s", place_id)

        raise HTTPException(
            status_code=404,
            detail="Menu not found",
        )

    # Basic structure validation
    if not isinstance(menu, dict) or "sections" not in menu:

        logger.warning(
            "menu_payload_invalid place_id=%s payload=%s",
            place_id,
            type(menu),
        )

        raise HTTPException(
            status_code=500,
            detail="Menu data corrupted",
        )

    return menu