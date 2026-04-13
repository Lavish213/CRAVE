from __future__ import annotations

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