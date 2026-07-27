from __future__ import annotations

# DEPRECATED / UNUSED: the only consumer of these schemas was
# app/api/routes/menus.py, which is itself deprecated (that router is not
# registered — see app/api/v1/routes/__init__.py — and was shadowed by
# app/api/v1/routes/places.py's live "/places/{place_id}/menu" route). A grep
# across the entire backend/ tree found zero other imports of MenuOut,
# MenuSectionOut, or MenuItemOut.
# Kept here for reference only — not wired up. Safe to delete along with
# app/api/routes/menus.py if no longer needed.

from typing import List, Optional

from pydantic import BaseModel


class MenuItemOut(BaseModel):
    name: str
    price_cents: Optional[int] = None
    currency: Optional[str] = None
    description: Optional[str] = None
    confidence: float


class MenuSectionOut(BaseModel):
    name: str
    items: List[MenuItemOut]


class MenuOut(BaseModel):
    sections: List[MenuSectionOut]
    item_count: int