from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.query.category_query import list_categories
from app.api.v1.schemas.categories import CategoriesResponse, CategoryOut


router = APIRouter(
    prefix="/categories",
    tags=["categories"],
)


@router.get(
    "",
    response_model=CategoriesResponse,
    summary="List categories",
)
def get_categories(
    db: Session = Depends(get_db),
) -> CategoriesResponse:
    """
    Returns all active categories.

    Guarantees
    ----------
    • deterministic ordering
    • read-only endpoint
    """

    categories = list_categories(db)

    items = [
        CategoryOut.model_validate(c, from_attributes=True)
        for c in categories
    ]

    return CategoriesResponse(
        total=len(items),
        items=items,
    )