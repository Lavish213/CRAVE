from __future__ import annotations

from typing import Dict, List, Optional, TypedDict


class SchemaRestaurant(TypedDict, total=False):

    name: str
    address: str
    telephone: str
    url: str
    servesCuisine: List[str]
    menu: str
    priceRange: str


class SchemaMenuItem(TypedDict, total=False):

    name: str
    description: Optional[str]
    price: Optional[str]
    currency: Optional[str]
    category: Optional[str]


class SchemaMenu(TypedDict, total=False):

    name: str
    items: List[SchemaMenuItem]